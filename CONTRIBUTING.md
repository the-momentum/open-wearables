# Contributing to Open Wearables

Thank you for your interest in contributing to Open Wearables!

Contributions are very welcome. Before you start, though, please **spend five minutes reading what's below** - it makes life easier for all of us. Thank you! ❤️

There is more than one way to help, and all of them count - whatever your experience level:

1. Reporting bugs and suggesting features
2. Joining discussions and sharing your perspective on where the project should go
3. Hanging out on [Discord](https://discord.gg/qrcfFnNE6H) and helping other users with their questions
4. Improving the documentation
5. Writing code

A note on our capacity: every pull request is reviewed manually by a core contributor, and as the project grows, review time has become our main bottleneck. The guidelines below exist to make sure your effort goes into something we can actually merge, and that reviewing a change doesn't cost more than the change itself. They are not meant to discourage you from contributing. We would much rather invest our time in people who want to stay involved with the project than in one-off submissions.

## Before You Start

- **Check what's already in flight.** Search [existing PRs](https://github.com/the-momentum/open-wearables/pulls) and [issues](https://github.com/the-momentum/open-wearables/issues), and drop by [Discord](https://discord.gg/qrcfFnNE6H) to see whether someone is already on it and whether the direction fits the roadmap.
- **Get a go-ahead before you start.** Comment on the issue or ask on Discord, and wait for someone from the core team to confirm. Some issues might be planned for core contributors, or depend on work you can't see from the outside, so this saves you building something we can't take.
- **Found a bug, or thinking about a feature? Open an issue first.** For a bug, describe the problem so we can agree on what is actually broken before talking about a fix. For a feature, describe the use case and wait for a reply - not every idea fits the roadmap, and hearing that before you build it is much cheaper than hearing it after.

See [Reporting Issues](./contributing/issues.md) and the [Pull Request Guidelines](./contributing/pull-requests.md) for templates and conventions.

## Before You Open a PR

> **Please run your change before you submit it.** Untested contributions are by far the most common reason we send a PR back. Code that has never actually been executed - not by the test suite, not by hand - isn't ready for review, however good it looks.

- **Exercise the change by hand.** Call the endpoint, click through the flow, sync against a real provider account - whatever your change touches. A green test suite is not the same thing as a working feature. Where it makes sense, show the proof in the PR description or a comment - a log excerpt, a screenshot, a sample response - **with all secrets and sensitive personal data stripped out.**
- **Make sure the tests pass locally.** See the [Testing guide](./contributing/testing.md) for how to run them.
- **Add tests for new behaviour.** If you're changing how something works, something should fail when you break it.

See the [Pull Request Guidelines](./contributing/pull-requests.md) for conventions and what the PR template asks for.

## Code Review Process

1. **CodeRabbit reviews first.** Every PR gets an automated first-round review. Please go through its comments, keeping in mind that not all of them will be correct. Working through them is also a good way to get familiar with the codebase. Once you have addressed this feedback, your PR moves on to manual review.
2. **CI for new contributors.** The first time you contribute, a committer needs to trigger the remaining CI jobs for you. This usually happens within 24 hours.
3. **Manual review by a core contributor.** Please respond to all feedback. Changing the code is not mandatory - if you disagree, say so; discussion is welcome. PRs with no response from the author for more than 7 days will be closed. You are welcome to reopen them later.
4. **Merge.** Once approved, a core contributor merges your change, usually within 24 hours.

When responding to review comments - especially the less obvious ones - a few words explaining your reasoning go a long way.

## AI-Assisted Contributions

We are open to AI-assisted contributions. Open Wearables itself was built with substantial AI involvement. That said, what works well in our day-to-day work does not always translate to external contributions, so we ask for a few things:

1. **Disclose it.** Let us know what you used - tool and model.
2. **Understand what you are submitting.** As the PR author, you should understand the core ideas of your change and be able to explain the decisions behind it during review.
3. **Flag what you are unsure about.** It is perfectly fine not to understand every line, or to be unsure about something because you are not fluent in Python. If that is the case, leave a comment on the relevant parts of the code so a reviewer knows where to look and can explain it to you.
4. **Be human when you talk to us!** :) Use whatever tools you like while writing the code, but please answer review comments yourself. A generated reply to a question a reviewer spent real time on comes across as disrespectful, and it rarely answers the question anyway.

### Sometimes an issue is the better contribution

AI output is only ever as good as the judgement applied to it. So if you can't tell whether your diff is any good, open a well-described issue instead: a real contribution, and usually the fastest way to get the thing built or fixed.

## Development

- [Setting Up Your Environment](./contributing/developing.md)
- [Testing](./contributing/testing.md)
- [Code Style & Linting](./contributing/linting.md)

## Extending

- [Adding a New Provider](./docs/dev-guides/how-to-add-new-provider.mdx)
