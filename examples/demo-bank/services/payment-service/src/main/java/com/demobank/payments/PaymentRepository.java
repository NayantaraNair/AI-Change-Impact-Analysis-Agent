package com.demobank.payments;

import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

/**
 * Persistence boundary for accepted transfer instructions.
 * Account/request uniqueness is also enforced by the database.
 * Queries returning entities remain inside the service transaction.
 */
@Repository
public interface PaymentRepository extends JpaRepository<Payment, UUID> {
    /** Locate an earlier instruction when a caller retries a request. */
    Optional<Payment> findByAccountIdAndRequestId(UUID accountId, UUID requestId);

    /** Return a bounded account history ordered by acceptance time. */
    List<Payment> findByAccountIdOrderByCreatedAtDesc(UUID accountId, Pageable page);

    /** Support operational reporting without loading every payment row. */
    long countByAccountIdAndStatus(UUID accountId, String status);
}
