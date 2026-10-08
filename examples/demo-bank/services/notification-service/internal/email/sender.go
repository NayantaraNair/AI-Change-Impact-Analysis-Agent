// Package email sends plain-text service notices through an internal mail gateway.
package email

import (
    "bytes"
    "context"
    "encoding/json"
    "fmt"
    "io"
    "net/http"
    "net/mail"
    "strings"
)

type EmailSender struct {
    GatewayURL string
    Client     *http.Client
}

// Send does not log recipient addresses or rendered message content.
func (s *EmailSender) Send(ctx context.Context, recipient string, message string) error {
    address, err := mail.ParseAddress(recipient)
    if err != nil || address.Address != recipient || len(message) == 0 || len(message) > 10000 {
        return fmt.Errorf("invalid email delivery fields")
    }
    payload, err := json.Marshal(map[string]string{
        "to": recipient, "subject": "Demo Bank service notice", "text": message,
    })
    if err != nil {
        return fmt.Errorf("cannot encode email request")
    }
    request, err := http.NewRequestWithContext(ctx, http.MethodPost,
        strings.TrimRight(s.GatewayURL, "/")+"/messages", bytes.NewReader(payload))
    if err != nil {
        return fmt.Errorf("cannot construct email request")
    }
    request.Header.Set("Content-Type", "application/json")
    response, err := s.Client.Do(request)
    if err != nil {
        return fmt.Errorf("email gateway request failed")
    }
    defer response.Body.Close()
    io.Copy(io.Discard, io.LimitReader(response.Body, 4096))
    if response.StatusCode < 200 || response.StatusCode >= 300 {
        return fmt.Errorf("email gateway rejected delivery")
    }
    return nil
}
