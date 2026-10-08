// Package templates owns reviewed customer-facing notification copy.
package templates

import (
    "bytes"
    "fmt"
    "text/template"
)

type TemplateStore struct {
    messages map[string]*template.Template
    required map[string][]string
}

func NewTemplateStore() *TemplateStore {
    sources := map[string]string{
        "password_reset": "Demo Bank: a password reset was requested. Visit {{.reset_url}}. If you did not request this, contact support.",
        "login_alert": "Demo Bank: your account was accessed at {{.occurred_at}}. Contact support if this was not you.",
    }
    store := &TemplateStore{
        messages: make(map[string]*template.Template),
        required: map[string][]string{
            "password_reset": {"reset_url"},
            "login_alert": {"occurred_at"},
        },
    }
    for name, source := range sources {
        store.messages[name] = template.Must(template.New(name).Option("missingkey=error").Parse(source))
    }
    return store
}

// Render refuses unknown templates and missing values before any provider call.
func (s *TemplateStore) Render(name string, values map[string]string) (string, error) {
    message, ok := s.messages[name]
    if !ok {
        return "", fmt.Errorf("unknown notification template")
    }
    for _, key := range s.required[name] {
        if values[key] == "" {
            return "", fmt.Errorf("missing notification value")
        }
    }
    var output bytes.Buffer
    if err := message.Execute(&output, values); err != nil {
        return "", fmt.Errorf("notification rendering failed")
    }
    return output.String(), nil
}
