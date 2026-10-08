package com.demobank.cards

import java.time.OffsetDateTime
import java.util.UUID
import jakarta.persistence.Column
import jakarta.persistence.Entity
import jakarta.persistence.EnumType
import jakarta.persistence.Enumerated
import jakarta.persistence.Id
import jakarta.persistence.Table
import jakarta.persistence.Version

enum class CardStatus { ACTIVE, FROZEN, CLOSED }

/** Only an opaque processor reference and the display suffix are stored here. */
@Entity
@Table(name = "cards")
data class Card(
    @Id
    val id: UUID = UUID.randomUUID(),

    @Column(name = "customer_id", nullable = false)
    val customerId: UUID = UUID.randomUUID(),

    @Column(name = "account_id", nullable = false)
    val accountId: UUID = UUID.randomUUID(),

    @Column(name = "processor_reference", nullable = false, unique = true, length = 120)
    val processorReference: String = "",

    @Column(name = "last_four", nullable = false, length = 4)
    val lastFour: String = "",

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 16)
    var status: CardStatus = CardStatus.ACTIVE,

    @Column(name = "frozen_at")
    var frozenAt: OffsetDateTime? = null,

    @Column(name = "created_at", nullable = false)
    val createdAt: OffsetDateTime = OffsetDateTime.now(),

    @Version
    var version: Long = 0
)
