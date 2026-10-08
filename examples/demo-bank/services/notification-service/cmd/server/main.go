// Notification API used by the authentication service and other bank workloads.
package main

import (
    "context"
    "encoding/json"
    "io"
    "log"
    "net/http"
    "os"
    "time"

    "demobank.example/notification-service/internal/email"
    "demobank.example/notification-service/internal/sms"
    "demobank.example/notification-service/internal/templates"
)

type deliveryRequest struct {
    Recipient string            `json:"recipient"`
    Template  string            `json:"template"`
    Values    map[string]string `json:"values"`
}

type sendMessage func(context.Context, string, string) error

func deliveryHandler(store *templates.TemplateStore, send sendMessage) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        if r.Method != http.MethodPost {
            w.Header().Set("Allow", http.MethodPost)
            http.Error(w, "POST required", http.StatusMethodNotAllowed)
            return
        }
        r.Body = http.MaxBytesReader(w, r.Body, 16*1024)
        defer r.Body.Close()
        decoder := json.NewDecoder(r.Body)
        decoder.DisallowUnknownFields()
        var request deliveryRequest
        if err := decoder.Decode(&request); err != nil || request.Recipient == "" {
            http.Error(w, "Invalid delivery request", http.StatusBadRequest)
            return
        }
        if err := decoder.Decode(new(any)); err != io.EOF {
            http.Error(w, "Only one JSON object is accepted", http.StatusBadRequest)
            return
        }
        message, err := store.Render(request.Template, request.Values)
        if err != nil {
            http.Error(w, "Invalid message template", http.StatusBadRequest)
            return
        }
        if err := send(r.Context(), request.Recipient, message); err != nil {
            http.Error(w, "Delivery gateway unavailable", http.StatusBadGateway)
            return
        }
        w.Header().Set("Content-Type", "application/json")
        w.WriteHeader(http.StatusAccepted)
        json.NewEncoder(w).Encode(map[string]string{"status": "accepted"})
    }
}

func main() {
    smsURL, emailURL := os.Getenv("SMS_GATEWAY_URL"), os.Getenv("EMAIL_GATEWAY_URL")
    if smsURL == "" || emailURL == "" {
        log.Fatal("Delivery gateway configuration is required")
    }
    client := &http.Client{Timeout: 4 * time.Second}
    store := templates.NewTemplateStore()
    smsSender := &sms.SmsSender{GatewayURL: smsURL, Client: client}
    emailSender := &email.EmailSender{GatewayURL: emailURL, Client: client}

    http.HandleFunc("/notify/sms", deliveryHandler(store, smsSender.Send))
    http.HandleFunc("/notify/email", deliveryHandler(store, emailSender.Send))

    server := &http.Server{
        Addr:              ":8080",
        ReadHeaderTimeout: 3 * time.Second,
        ReadTimeout:       5 * time.Second,
        WriteTimeout:      8 * time.Second,
        IdleTimeout:       60 * time.Second,
    }
    log.Fatal(server.ListenAndServe())
}
