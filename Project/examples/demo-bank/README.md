# Demo Bank

Demo Bank is a fictional retail banking platform
used to demonstrate source-based change-impact analysis.
Its services use familiar framework conventions so that
routes, classes, dependencies, and database tables can be
discovered with straightforward source indexing.
The platform contains five services:
`auth-service` (Python and FastAPI) handles password login,
session revocation, token refresh, and account lockout;
`payment-service` (Java and Spring Boot) submits transfers,
screens fraud, and enforces daily payment limits;
`customer-service` (TypeScript, Express, and TypeORM) manages
customer profiles, contact details, and staff-reviewed phone verification;
`notification-service` (Go) delivers SMS and email messages
using centrally managed templates;
and `card-service` (Kotlin and Spring) retrieves and freezes cards.
The standard daily transfer allowance is AED 25,000,
measured against the account's Dubai calendar day.
Password reset is a deliberately unfinished route returning HTTP 501.
The SQL migrations describe a shared PostgreSQL demonstration database,
while each service owns the tables associated with its domain.
All names and example addresses are fictional.
This folder is an indexing fixture rather than a deployable application:
production identity middleware, provider credentials, deployment wiring,
and operational configuration are intentionally left to the host environment.
