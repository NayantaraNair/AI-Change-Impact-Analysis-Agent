package com.demobank.cards

import java.util.UUID
import jakarta.persistence.LockModeType
import org.springframework.data.jpa.repository.JpaRepository
import org.springframework.data.jpa.repository.Lock
import org.springframework.data.jpa.repository.Query
import org.springframework.data.repository.query.Param
import org.springframework.stereotype.Repository

/** Ownership is part of each query so that card IDs cannot bypass access checks. */
@Repository
interface CardRepository : JpaRepository<Card, UUID> {
    fun findByIdAndCustomerId(cardId: UUID, customerId: UUID): Card?

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("SELECT c FROM Card c WHERE c.id = :cardId AND c.customerId = :customerId")
    fun findOwnedForUpdate(
        @Param("cardId") cardId: UUID,
        @Param("customerId") customerId: UUID
    ): Card?

    /** Bounded status counts support the customer's card summary. */
    fun countByCustomerIdAndStatus(customerId: UUID, status: CardStatus): Long
}
