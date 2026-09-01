# Google Health API endpoint paths. {data_type} is the kebab-case data type;
# {project} is the GCP project number.
LIST_ENDPOINT = "/v4/users/me/dataTypes/{data_type}/dataPoints"
ROLLUP_ENDPOINT = "/v4/users/me/dataTypes/{data_type}/dataPoints:rollUp"
RECONCILE_ENDPOINT = "/v4/users/me/dataTypes/{data_type}/dataPoints:reconcile"
IDENTITY_ENDPOINT = "/v4/users/me/identity"
SUBSCRIBERS_ENDPOINT = "/v4/projects/{project}/subscribers"
