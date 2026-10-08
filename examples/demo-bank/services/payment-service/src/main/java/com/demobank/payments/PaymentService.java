package com.demobank.payments;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

/** Reserve daily allowance and persist the accepted instruction in one transaction. */
@Service
public class PaymentService {
    private final PaymentRepository payments;
    private final DailyLimitUsageRepository usage;
    private final DailyLimitPolicy policy;
    private final FraudScreeningClient fraud;

    public PaymentService(PaymentRepository payments, DailyLimitUsageRepository usage,
                          DailyLimitPolicy policy, FraudScreeningClient fraud) {
        this.payments = payments;
        this.usage = usage;
        this.policy = policy;
        this.fraud = fraud;
    }

    @Transactional
    public Payment submit(UUID accountId, String beneficiary, BigDecimal amount,
                          String currency, UUID requestId) {
        policy.validateTransfer(amount, currency);
        LocalDate day = policy.businessDate();
        // Materializing and locking this row serializes transfers for an account/day.
        usage.ensureRow(accountId, day, DailyLimitUsage.key(accountId, day));
        DailyLimitUsage current = usage.findForUpdate(accountId, day).orElseThrow();
        var previous = payments.findByAccountIdAndRequestId(accountId, requestId);
        if (previous.isPresent()) {
            Payment existing = previous.get();
            if (!existing.matches(beneficiary, amount, currency)) {
                throw new ResponseStatusException(HttpStatus.CONFLICT, "Request ID already used");
            }
            return existing;
        }
        policy.requireAvailable(current.getUsedAmount(), amount);
        fraud.requireApproval(accountId, beneficiary, amount, currency, requestId);
        current.reserve(amount);
        return payments.save(new Payment(accountId, beneficiary, amount, currency, requestId));
    }

    @Transactional(readOnly = true)
    public Payment get(UUID id) {
        return payments.findById(id).orElseThrow(() ->
                new ResponseStatusException(HttpStatus.NOT_FOUND, "Payment not found"));
    }

    @Transactional(readOnly = true)
    public DailyLimitPolicy.LimitSnapshot limits(UUID accountId) {
        LocalDate day = policy.businessDate();
        BigDecimal spent = usage.findByAccountIdAndUsageDate(accountId, day)
                .map(DailyLimitUsage::getUsedAmount).orElse(BigDecimal.ZERO);
        return policy.snapshot(day, spent);
    }
}
