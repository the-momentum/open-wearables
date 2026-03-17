#!/usr/bin/env python3
"""Replay raw payloads stored in S3 back through the SDK sync endpoint.

Standalone script - no imports from app.* required. Just boto3 + httpx + stdlib.

Usage:
    uv run --with boto3,httpx python scripts/replay_raw_payloads.py \
        --user-id <UUID> \
        [--target-user-id <UUID>] \
        --api-url http://localhost:8000 \
        --api-key sk-... \
        --s3-bucket my-bucket \
        [--s3-prefix raw-payloads] \
        [--s3-endpoint-url https://...] \
        [--aws-region eu-north-1] \
        [--aws-access-key-id AKIA...] \
        [--aws-secret-access-key ...] \
        [--provider apple] \
        [--source sdk] \
        [--date-from 2025-01-01] \
        [--date-to 2025-01-31] \
        [--delay 1.0] \
        [--dry-run] \
        [--limit 10]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date, datetime
from typing import Any

import boto3
import httpx


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replay S3-stored raw payloads through the SDK sync endpoint",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Required
    parser.add_argument("--user-id", required=True, help="S3 user ID whose payloads to read")
    parser.add_argument("--target-user-id", help="User ID to send payloads to (defaults to --user-id)")
    parser.add_argument(
        "--api-url", default="http://localhost:8000", help="Backend API base URL (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("OPEN_WEARABLES_API_KEY"),
        help="API key (or set OPEN_WEARABLES_API_KEY env var)",
    )
    parser.add_argument(
        "--s3-bucket",
        default=os.environ.get("RAW_PAYLOAD_S3_BUCKET") or os.environ.get("AWS_BUCKET_NAME"),
        help="S3 bucket name (or set RAW_PAYLOAD_S3_BUCKET / AWS_BUCKET_NAME env var)",
    )

    # S3 config
    parser.add_argument(
        "--s3-prefix",
        default=os.environ.get("RAW_PAYLOAD_S3_PREFIX", "raw-payloads"),
        help="S3 key prefix (default: raw-payloads)",
    )
    parser.add_argument(
        "--s3-endpoint-url",
        default=os.environ.get("RAW_PAYLOAD_S3_ENDPOINT_URL"),
        help="S3 endpoint URL for S3-compatible storage",
    )
    parser.add_argument(
        "--aws-region", default=os.environ.get("AWS_REGION", "eu-north-1"), help="AWS region (default: eu-north-1)"
    )
    parser.add_argument(
        "--aws-access-key-id",
        default=os.environ.get("AWS_ACCESS_KEY_ID"),
        help="AWS access key ID (or set AWS_ACCESS_KEY_ID env var)",
    )
    parser.add_argument(
        "--aws-secret-access-key",
        default=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        help="AWS secret access key (or set AWS_SECRET_ACCESS_KEY env var)",
    )

    # Filters
    parser.add_argument("--provider", help="Filter by provider (e.g. apple, samsung, google)")
    parser.add_argument("--source", help="Filter by source (e.g. sdk, webhook)")
    parser.add_argument("--date-from", type=date.fromisoformat, help="Filter payloads from this date (YYYY-MM-DD)")
    parser.add_argument("--date-to", type=date.fromisoformat, help="Filter payloads up to this date (YYYY-MM-DD)")

    # Behavior
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between requests in seconds (default: 1.0)")
    parser.add_argument("--dry-run", action="store_true", help="List payloads without sending them")
    parser.add_argument("--limit", type=int, help="Maximum number of payloads to replay")

    args = parser.parse_args()

    if not args.api_key:
        parser.error("--api-key is required (or set OPEN_WEARABLES_API_KEY env var)")
    if not args.s3_bucket:
        parser.error("--s3-bucket is required (or set RAW_PAYLOAD_S3_BUCKET env var)")
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be a positive integer")
    if not args.target_user_id:
        args.target_user_id = args.user_id

    return args


def build_s3_prefix(base_prefix: str, provider: str | None, source: str | None) -> str:
    """Build the S3 key prefix for listing objects.

    Key format: {prefix}/{provider}/{source}/{YYYY-MM-DD}/{user_id}/{uuid}.json
    We build the deepest prefix we can from the filters to narrow the listing.
    If provider or source is not specified, we list from the broadest level
    and filter client-side.
    """
    parts = [base_prefix]
    if provider:
        parts.append(provider)
        if source:
            parts.append(source)
    return "/".join(parts) + "/"


def parse_key_date(key: str) -> date | None:
    """Extract the date component from an S3 key path."""
    parts = key.split("/")
    for part in parts:
        try:
            return date.fromisoformat(part)
        except ValueError:
            continue
    return None


def matches_filters(
    key: str,
    user_id: str,
    provider: str | None,
    source: str | None,
    date_from: date | None,
    date_to: date | None,
) -> bool:
    """Check if an S3 key matches all specified filters."""
    # Must contain the user_id in the path
    if f"/{user_id}/" not in key:
        return False

    parts = key.split("/")

    # When provider/source not baked into prefix, check them in the key
    if provider and provider not in parts:
        return False
    if source and source not in parts:
        return False

    # Date range filtering
    if date_from or date_to:
        key_date = parse_key_date(key)
        if key_date is None:
            return False
        if date_from and key_date < date_from:
            return False
        if date_to and key_date > date_to:
            return False

    return True


def list_payloads(s3_client: Any, bucket: str, prefix: str, args: argparse.Namespace) -> list[tuple[str, datetime]]:
    """List and filter S3 keys matching the given criteria. Returns (key, last_modified) tuples."""
    entries: list[tuple[str, datetime]] = []
    paginator = s3_client.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if not key.endswith(".json"):
                continue
            if matches_filters(key, args.user_id, args.provider, args.source, args.date_from, args.date_to):
                entries.append((key, obj["LastModified"]))

    # Sort by upload timestamp (original arrival order)
    entries.sort(key=lambda e: e[1])

    if args.limit is not None:
        entries = entries[: args.limit]

    return entries


def replay_payload(http_client: Any, api_url: str, api_key: str, user_id: str, payload_bytes: bytes) -> tuple[int, str]:
    """Send a payload to the SDK sync endpoint. Returns (status_code, response_text)."""
    url = f"{api_url}/api/v1/sdk/users/{user_id}/sync"
    resp = http_client.post(
        url,
        content=payload_bytes,
        headers={
            "X-Open-Wearables-API-Key": api_key,
            "Content-Type": "application/json",
        },
    )
    return resp.status_code, resp.text


def format_size(size_bytes: int) -> str:
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} bytes"


def main() -> None:
    args = parse_args()

    # Create S3 client
    s3_kwargs: dict = {"region_name": args.aws_region}
    if args.s3_endpoint_url:
        s3_kwargs["endpoint_url"] = args.s3_endpoint_url
    if args.aws_access_key_id and args.aws_secret_access_key:
        s3_kwargs["aws_access_key_id"] = args.aws_access_key_id
        s3_kwargs["aws_secret_access_key"] = args.aws_secret_access_key
    s3_client = boto3.client("s3", **s3_kwargs)

    # Build prefix and list payloads
    prefix = build_s3_prefix(args.s3_prefix, args.provider, args.source)
    print(f"Listing payloads in s3://{args.s3_bucket}/{prefix}")
    print(f"  Source user ID: {args.user_id}")
    if args.target_user_id != args.user_id:
        print(f"  Target user ID: {args.target_user_id}")
    if args.provider:
        print(f"  Provider: {args.provider}")
    if args.source:
        print(f"  Source: {args.source}")
    if args.date_from:
        print(f"  From: {args.date_from}")
    if args.date_to:
        print(f"  To: {args.date_to}")

    entries = list_payloads(s3_client, args.s3_bucket, prefix, args)

    if not entries:
        print("\nNo payloads found matching the filters.")
        sys.exit(0)

    total = len(entries)
    print(f"\nFound {total} payload(s)")

    if args.dry_run:
        print("\n[DRY RUN] Payloads that would be replayed:")
        for i, (key, last_modified) in enumerate(entries, 1):
            ts = last_modified.strftime("%Y-%m-%d %H:%M:%S")
            print(f"  {i}. {key} (uploaded: {ts})")
        sys.exit(0)

    # Replay payloads
    print(f"\nReplaying to {args.api_url} (delay: {args.delay}s)")
    print("-" * 60)

    success = 0
    failed = 0
    total_bytes = 0

    with httpx.Client(timeout=30.0) as http_client:
        for i, (key, last_modified) in enumerate(entries, 1):
            ts = last_modified.strftime("%Y-%m-%d %H:%M:%S")
            try:
                obj = s3_client.get_object(Bucket=args.s3_bucket, Key=key)
                payload_bytes = obj["Body"].read()
                size = len(payload_bytes)
                total_bytes += size

                # Validate JSON
                json.loads(payload_bytes)

                status_code, response_text = replay_payload(
                    http_client, args.api_url, args.api_key, args.target_user_id, payload_bytes
                )

                if 200 <= status_code < 300:
                    success += 1
                    print(f"  [{i}/{total}] OK {status_code} - {ts} - {format_size(size)}")
                else:
                    failed += 1
                    detail = response_text[:200]
                    print(f"  [{i}/{total}] FAIL {status_code} - {ts} - {format_size(size)} - {detail}")

            except json.JSONDecodeError:
                failed += 1
                print(f"  [{i}/{total}] SKIP - invalid JSON: {key}")
            except Exception as e:
                failed += 1
                print(f"  [{i}/{total}] ERROR - {key}: {e}")

            if i < total and args.delay > 0:
                time.sleep(args.delay)

    # Summary
    print("-" * 60)
    print(f"Done. {success} succeeded, {failed} failed, {format_size(total_bytes)} total")


if __name__ == "__main__":
    main()
