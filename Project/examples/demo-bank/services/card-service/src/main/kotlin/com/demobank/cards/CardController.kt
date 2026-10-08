package com.demobank.cards

import java.time.OffsetDateTime
import java.util.UUID
import org.springframework.http.HttpStatus
import org.springframework.security.core.annotation.AuthenticationPrincipal
import org.springframework.security.oauth2.jwt.Jwt
import org.springframework.web.bind.annotation.GetMapping
import org.springframework.web.bind.annotation.PathVariable
import org.springframework.web.bind.annotation.PostMapping
import org.springframework.web.bind.annotation.RestController
import org.springframework.web.server.ResponseStatusException

/** Self-service card controls scoped to the authenticated customer's profile. */
@RestController
class CardController(private val cards: CardService) {
    @PostMapping("/cards/{cardId}/freeze")
    fun freeze(@PathVariable cardId: UUID, @AuthenticationPrincipal principal: Jwt?): CardView {
        return view(cards.freeze(cardId, customerId(principal)))
    }

    @GetMapping("/cards/{cardId}")
    fun get(@PathVariable cardId: UUID, @AuthenticationPrincipal principal: Jwt?): CardView {
        return view(cards.get(cardId, customerId(principal)))
    }

    private fun customerId(principal: Jwt?): UUID {
        val claim = principal?.getClaimAsString("customer_id")
            ?: throw ResponseStatusException(HttpStatus.UNAUTHORIZED, "Customer identity required")
        return try {
            UUID.fromString(claim)
        } catch (exception: IllegalArgumentException) {
            throw ResponseStatusException(HttpStatus.UNAUTHORIZED, "Invalid customer identity")
        }
    }

    private fun view(card: Card) = CardView(
        card.id, card.lastFour, card.status, card.frozenAt
    )

    data class CardView(
        val id: UUID,
        val lastFour: String,
        val status: CardStatus,
        val frozenAt: OffsetDateTime?
    )
}
