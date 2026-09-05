# Security and Privacy

## Privacy model
The product is designed around local/self-hosted processing. Do not send real client data to external AI services.

## Data minimization
- process only required columns;
- redact or hash identifiers where practical;
- never put raw financial rows in application logs;
- default to short-lived working files;
- allow configured retention mode;
- provide a zero-persistence processing path where technically feasible.

## Important distinction
“Not used to train the model” is not the same as “never left the firm.” CA-Guard’s strongest privacy claim is achieved by keeping data local and avoiding external model calls for sensitive data.

## Railway limitation
Railway is hosted infrastructure. The demo must therefore use synthetic/public data. Do not market the Railway deployment as the private on-premise version.

## Security checks
- dependency audit;
- input validation;
- upload size/type limits;
- path traversal protection;
- safe filename handling;
- authentication for deployment where necessary;
- secret management via environment variables;
- redaction in logs;
- no secrets committed to git.
