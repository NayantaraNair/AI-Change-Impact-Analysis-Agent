package com.demobank.payments;

import java.math.BigDecimal;
import java.util.List;
import java.util.UUID;
import jakarta.validation.Valid;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.Digits;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

/** Transfer endpoints; gateway-issued account claims identify permitted debit accounts. */
@RestController
public class PaymentController {
    private final PaymentService payments;

    public PaymentController(PaymentService payments) {
        this.payments = payments;
    }

    @PostMapping("/payments")
    @ResponseStatus(HttpStatus.CREATED)
    public PaymentReceipt create(@Valid @RequestBody PaymentRequest request,
                                 @AuthenticationPrincipal Jwt principal) {
        requireAccount(principal, request.accountId());
        return receipt(payments.submit(request.accountId(), request.beneficiaryReference(),
                request.amount(), request.currency(), request.requestId()));
    }

    @GetMapping("/payments/{id}")
    public PaymentReceipt get(@PathVariable UUID id, @AuthenticationPrincipal Jwt principal) {
        Payment payment = payments.get(id);
        requireAccount(principal, payment.getAccountId());
        return receipt(payment);
    }

    @GetMapping("/accounts/{accountId}/limits")
    public DailyLimitPolicy.LimitSnapshot limits(@PathVariable UUID accountId,
                                               @AuthenticationPrincipal Jwt principal) {
        requireAccount(principal, accountId);
        return payments.limits(accountId);
    }

    private void requireAccount(Jwt principal, UUID accountId) {
        List<String> allowed = principal == null ? null : principal.getClaimAsStringList("account_ids");
        if (allowed == null || !allowed.contains(accountId.toString())) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Account access denied");
        }
    }

    private PaymentReceipt receipt(Payment payment) {
        return new PaymentReceipt(payment.getId(), payment.getAccountId(), payment.getAmount(),
                payment.getCurrency(), payment.getStatus());
    }

    public record PaymentRequest(
            @NotNull UUID accountId,
            @NotBlank @Size(max = 120) String beneficiaryReference,
            @NotNull @DecimalMin("0.01") @Digits(integer = 16, fraction = 2) BigDecimal amount,
            @NotBlank @Size(min = 3, max = 3) String currency,
            @NotNull UUID requestId) {}

    public record PaymentReceipt(UUID id, UUID accountId, BigDecimal amount,
                                 String currency, String status) {}
}
