package com.demobank.payments;

import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.UUID;
import jakarta.persistence.*;

/** An accepted transfer instruction; settlement is performed downstream. */
@Entity
@Table(name = "payments", uniqueConstraints =
        @UniqueConstraint(columnNames = {"account_id", "request_id"}))
public class Payment {
    @Id
    private UUID id;

    @Column(name = "account_id", nullable = false)
    private UUID accountId;

    @Column(name = "beneficiary_reference", nullable = false, length = 120)
    private String beneficiaryReference;

    @Column(nullable = false, precision = 18, scale = 2)
    private BigDecimal amount;

    @Column(nullable = false, length = 3)
    private String currency;

    @Column(nullable = false, length = 24)
    private String status;

    @Column(name = "request_id", nullable = false)
    private UUID requestId;

    @Column(name = "created_at", nullable = false)
    private OffsetDateTime createdAt;

    protected Payment() {}

    public Payment(UUID accountId, String beneficiary, BigDecimal amount,
                   String currency, UUID requestId) {
        this.id = UUID.randomUUID();
        this.accountId = accountId;
        this.beneficiaryReference = beneficiary;
        this.amount = amount;
        this.currency = currency;
        this.requestId = requestId;
        this.status = "ACCEPTED";
        this.createdAt = OffsetDateTime.now();
    }

    public boolean matches(String beneficiary, BigDecimal requestedAmount, String requestedCurrency) {
        return beneficiaryReference.equals(beneficiary) && amount.compareTo(requestedAmount) == 0
                && currency.equals(requestedCurrency);
    }

    public UUID getId() { return id; }
    public UUID getAccountId() { return accountId; }
    public BigDecimal getAmount() { return amount; }
    public String getCurrency() { return currency; }
    public String getStatus() { return status; }
}
