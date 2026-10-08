// Package sms adapts bank notification requests to an internal SMS gateway.
package sms

import (
    "bytes"
    "context"
    "encoding/json"
    "fmt"
    "io"
    "net/http"
    "regexp"
    "strings"
)

var phonePattern = regexp.MustCompile(`^\+[1-9][0-9]{7,14}$`)

type SmsSender struct {
    GatewayURL string
    Client     *http.Client
}

// Send returns only after the gateway has accepted a single service message.
func (s *SmsSender) Send(ctx context.Context, recipient string, message string) error {
    if !phonePattern.MatchString(recipient) || len(message) == 0 || len(message) > 1000 {
        return fmt.Errorf("invalid SMS delivery fields")
    }
    payload, err := json.Marshal(map[string]string{"to": recipient, "text": message})
    if err != nil {
        return fmt.Errorf("cannot encode SMS request")
    }
    request, err := http.NewRequestWithContext(ctx, http.MethodPost,
        strings.TrimRight(s.GatewayURL, "/")+"/messages", bytes.NewReader(payload))
    if err != nil {
        return fmt.Errorf("cannot construct SMS request")
    }
    request.Header.Set("Content-Type", "application/json")
    response, err := s.Client.Do(request)
    if err != nil {
        return fmt.Errorf("SMS gateway request failed")
    }
    defer response.Body.Close()
    io.Copy(io.Discard, io.LimitReader(response.Body, 4096))
    if response.StatusCode < 200 || response.StatusCode >= 300 {
        return fmt.Errorf("SMS gateway rejected delivery")
    }
    return nil
}
