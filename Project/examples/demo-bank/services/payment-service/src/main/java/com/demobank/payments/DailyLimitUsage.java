package com.demobank.payments;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.UUID;
import jakarta.persistence.*;

/** Persisted allowance consumption, updated under a database row lock. */
@Entity
@Table(name = "daily_limit_usage", uniqueConstraints =
        @UniqueConstraint(columnNames = {"account_id", "usage_date"}))
public class DailyLimitUsage {
    @Id
    @Column(length = 80)
    private String id;

    @Column(name = "account_id", nullable = false)
    private UUID accountId;

    @Column(name = "usage_date", nullable = false)
    private LocalDate usageDate;

    @Column(name = "used_amount", nullable = false, precision = 18, scale = 2)
    private BigDecimal usedAmount = BigDecimal.ZERO;

    protected DailyLimitUsage() {}

    public static String key(UUID accountId, LocalDate day) {
        return accountId + ":" + day;
    }

    public void reserve(BigDecimal amount) {
        usedAmount = usedAmount.add(amount);
    }

    public BigDecimal getUsedAmount() {
        return usedAmount;
    }
}
