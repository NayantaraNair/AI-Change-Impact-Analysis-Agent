package com.demobank.cards

import java.time.OffsetDateTime
import java.time.ZoneOffset
import java.util.UUID
import org.springframework.http.HttpStatus
import org.springframework.stereotype.Service
import org.springframework.transaction.annotation.Transactional
import org.springframework.web.server.ResponseStatusException

/** Card freeze is idempotent and never changes a closed card back to active. */
@Service
class CardService(private val repository: CardRepository) {
    @Transactional(readOnly = true)
    fun get(cardId: UUID, customerId: UUID): Card {
        return repository.findByIdAndCustomerId(cardId, customerId)
            ?: throw ResponseStatusException(HttpStatus.NOT_FOUND, "Card not found")
    }

    @Transactional
    fun freeze(cardId: UUID, customerId: UUID): Card {
        val card = repository.findOwnedForUpdate(cardId, customerId)
            ?: throw ResponseStatusException(HttpStatus.NOT_FOUND, "Card not found")
        when (card.status) {
            CardStatus.CLOSED -> throw ResponseStatusException(
                HttpStatus.CONFLICT, "A closed card cannot be frozen"
            )
            CardStatus.FROZEN -> return card
            CardStatus.ACTIVE -> {
                card.status = CardStatus.FROZEN
                card.frozenAt = OffsetDateTime.now(ZoneOffset.UTC)
            }
        }
        // The card authorization system reads persisted status before approving spend.
        return repository.save(card)
    }
}
