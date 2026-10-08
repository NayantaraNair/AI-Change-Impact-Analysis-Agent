package com.demobank.payments;

import java.time.LocalDate;
import java.util.Optional;
import java.util.UUID;
import jakarta.persistence.LockModeType;
import org.springframework.data.jpa.repository.*;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

/** PostgreSQL upsert avoids a race when the first two transfers arrive together. */
@Repository
public interface DailyLimitUsageRepository extends JpaRepository<DailyLimitUsage, String> {
    @Modifying
    @Query(value = "INSERT INTO daily_limit_usage (id, account_id, usage_date, used_amount) "
            + "VALUES (:id, :accountId, :day, 0) ON CONFLICT (account_id, usage_date) DO NOTHING",
            nativeQuery = true)
    void ensureRow(@Param("accountId") UUID accountId, @Param("day") LocalDate day,
                   @Param("id") String id);

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("SELECT u FROM DailyLimitUsage u WHERE u.accountId = :accountId AND u.usageDate = :day")
    Optional<DailyLimitUsage> findForUpdate(@Param("accountId") UUID accountId,
                                           @Param("day") LocalDate day);

    Optional<DailyLimitUsage> findByAccountIdAndUsageDate(UUID accountId, LocalDate day);
}
