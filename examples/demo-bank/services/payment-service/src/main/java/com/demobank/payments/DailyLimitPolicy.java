package com.demobank.payments;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.ZoneId;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ResponseStatusException;

/** Standard retail transfers share an AED 25,000 allowance per Dubai calendar day. */
@Component
public class DailyLimitPolicy {
    public static final BigDecimal STANDARD_DAILY_LIMIT = new BigDecimal("25000.00");
    private static final ZoneId BANK_TIME_ZONE = ZoneId.of("Asia/Dubai");

    public LocalDate businessDate() {
        return LocalDate.now(BANK_TIME_ZONE);
    }

    public void validateTransfer(BigDecimal amount, String currency) {
        if (!"AED".equals(currency)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Only AED transfers are supported");
        }
        if (amount == null || amount.signum() <= 0 || amount.scale() > 2) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Invalid transfer amount");
        }
    }

    public void requireAvailable(BigDecimal usedAmount, BigDecimal requestedAmount) {
        if (usedAmount.add(requestedAmount).compareTo(STANDARD_DAILY_LIMIT) > 0) {
            throw new ResponseStatusException(HttpStatus.UNPROCESSABLE_ENTITY,
                    "Daily transfer limit exceeded");
        }
    }

    public LimitSnapshot snapshot(LocalDate day, BigDecimal usedAmount) {
        BigDecimal remaining = STANDARD_DAILY_LIMIT.subtract(usedAmount).max(BigDecimal.ZERO);
        return new LimitSnapshot(day, "AED", STANDARD_DAILY_LIMIT, usedAmount, remaining);
    }

    public record LimitSnapshot(LocalDate date, String currency, BigDecimal dailyLimit,
                                BigDecimal usedAmount, BigDecimal remainingAmount) {}
}
