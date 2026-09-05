# Release and Deployment

## Local/private deployment
Primary privacy path:
- Docker Compose or equivalent single-host deployment;
- local database/storage;
- local analytics engine;
- local LLM adapter;
- no outbound transmission of sensitive financial data.

## Railway demo
Purpose: public portfolio/faculty/conference demonstration using synthetic/public data.

Current Railway facts must be rechecked during deployment because pricing/resource policies can change. As of the project research snapshot, Railway offers a $0 Free plan with limited monthly resources; a Free Trial includes a one-time credit grant. Do not build a business assumption around free hosting.

Source: https://docs.railway.com/pricing

## Neon
Use only for non-sensitive application metadata if required by the Railway demo. A private/local deployment should not require Neon.

## Release checklist
- tests green;
- no secrets in repo;
- demo data synthetic/public;
- privacy wording accurate;
- Docker build successful;
- Railway deployment successful;
- README deployment instructions updated;
- version tagged.
