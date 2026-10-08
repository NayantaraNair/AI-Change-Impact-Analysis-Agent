// Demo Bank notification-service module.
// This service intentionally uses only the Go standard library.
// HTTP provider adapters live under internal/sms and internal/email.
// Shared message rendering lives under internal/templates.
// The module path is fictional and is not an external dependency.
// No generated dependency lock file is needed for this fixture.

module demobank.example/notification-service

go 1.22

// Runtime configuration is injected by the hosting environment:
// SMS_GATEWAY_URL identifies the internal SMS delivery adapter.
// EMAIL_GATEWAY_URL identifies the internal email delivery adapter.
// Gateway authentication is supplied by deployment infrastructure.
// Recipient information is never included in operational log messages.
// Message templates contain service notices and recovery copy.
// Templates are rendered before forwarding a message to a gateway.
// Provider failures are returned as HTTP 502 to the calling service.
// The HTTP client uses a bounded delivery timeout.
// The server rejects methods other than POST for message delivery.
// Request bodies are size-limited and validated before dispatch.
// The server does not persist delivery payloads or customer addresses.
// A successful response means that the gateway accepted the message.
// Final delivery receipts are owned by the external gateway.
