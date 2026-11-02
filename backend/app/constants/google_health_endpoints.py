# Google Health API endpoint paths. {data_type} is the kebab-case data type;
# {project} is the GCP project number.
LIST_ENDPOINT = "/v4/users/me/dataTypes/{data_type}/dataPoints"
ROLLUP_ENDPOINT = "/v4/users/me/dataTypes/{data_type}/dataPoints:rollUp"
DAILY_ROLLUP_ENDPOINT = "/v4/users/me/dataTypes/{data_type}/dataPoints:dailyRollUp"
RECONCILE_ENDPOINT = "/v4/users/me/dataTypes/{data_type}/dataPoints:reconcile"
IDENTITY_ENDPOINT = "/v4/users/me/identity"
SUBSCRIBERS_ENDPOINT = "/v4/projects/{project}/subscribers"

# OAuth scope covering the nutrition data types (nutrition-log, hydration-log). Ren's
# OAuth client deliberately does not request it, so a connection whose granted scope
# lacks it must skip those types rather than sync 403s on every run.
NUTRITION_SCOPE = "https://www.googleapis.com/auth/googlehealth.nutrition.readonly"
