package com.demobank.payments;

import java.math.BigDecimal;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.web.server.ResponseStatusException;

/** Adapter to a deployment-provided fraud screening system. */
@Component
public class FraudScreeningClient {
    private final RestClient http;

    public FraudScreeningClient(@Value("${fraud.base-url}") String baseUrl) {
        this.http = RestClient.builder().baseUrl(baseUrl)
                .requestFactory(new org.springframework.http.client.JdkClientHttpRequestFactory(
                        java.net.http.HttpClient.newBuilder()
                                .connectTimeout(java.time.Duration.ofSeconds(2)).build()))
                .build();
    }

    public void requireApproval(UUID accountId, String beneficiary, BigDecimal amount,
                                String currency, UUID requestId) {
        FraudDecision decision;
        try {
            decision = http.post().uri("/fraud/check")
                    .body(new FraudRequest(accountId, beneficiary, amount, currency, requestId))
                    .retrieve().body(FraudDecision.class);
        } catch (RestClientException exception) {
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE,
                    "Fraud screening unavailable");
        }
        if (decision == null || !"APPROVE".equals(decision.outcome())) {
            throw new ResponseStatusException(HttpStatus.UNPROCESSABLE_ENTITY,
                    "Payment requires fraud review");
        }
    }

    private record FraudRequest(UUID accountId, String beneficiary, BigDecimal amount,
                                String currency, UUID requestId) {}
    private record FraudDecision(String outcome, String reference) {}
}
