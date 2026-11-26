package com.microservices_example_app.booking;

import com.microservices_example_app.booking.dto.AvailabilityStatus;
import com.microservices_example_app.booking.dto.EventAvailabilityResponseDto;
import com.microservices_example_app.booking.dto.ZoneAvailabilityDto;
import com.microservices_example_app.booking.exceptions.NotFoundException;
import com.microservices_example_app.booking.model.Event;
import com.microservices_example_app.booking.model.Venue;
import com.microservices_example_app.booking.model.Zone;
import com.microservices_example_app.booking.producers.BookingCatalogProducer;
import com.microservices_example_app.booking.producers.NotificationKafkaUserProducer;
import com.microservices_example_app.booking.repository.EventRepository;
import com.microservices_example_app.booking.repository.TicketRepository;
import com.microservices_example_app.booking.repository.VenueRepository;
import com.microservices_example_app.booking.repository.ZoneAvailabilityProjection;
import com.microservices_example_app.booking.service.EventService;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class EventAvailabilityServiceTest {

    @Mock
    private EventRepository eventRepository;

    @Mock
    private VenueRepository venueRepository;

    @Mock
    private NotificationKafkaUserProducer kafkaUserProducer;

    @Mock
    private BookingCatalogProducer catalogProducer;

    @Mock
    private TicketRepository ticketRepository;

    @InjectMocks
    private EventService eventService;

    @Test
    void availability_shouldReturnSoldOutWhenNoActiveTickets() {
        stubEvent(100L, 150);
        when(ticketRepository.aggregateActiveByZone(100L)).thenReturn(List.of());

        EventAvailabilityResponseDto result = eventService.availability(100L, 2);

        assertThat(result.getEventId()).isEqualTo(100L);
        assertThat(result.getStatus()).isEqualTo(AvailabilityStatus.SOLD_OUT);
        assertThat(result.getCapacity()).isEqualTo(150);
        assertThat(result.getZones()).isEmpty();
    }

    @Test
    void availability_shouldReturnFewLeftWhenTotalIsBelowThreshold() {
        // 5 active tickets, party of 2 fits, but the total is under 10.
        stubEvent(100L, 150);
        stubZones(projection(Zone.BASIC, 5, "40.00"));

        EventAvailabilityResponseDto result = eventService.availability(100L, 2);

        assertThat(result.getStatus()).isEqualTo(AvailabilityStatus.FEW_LEFT);
        assertThat(result.getZones()).hasSize(1);
        assertThat(result.getZones().getFirst().getSeatsLeft()).isEqualTo(5L);
    }

    @Test
    void availability_shouldReturnInsufficientWhenNoZoneFitsParty() {
        // Total 11 (> threshold) but the biggest zone holds 9 < 10 requested.
        stubEvent(100L, 150);
        stubZones(projection(Zone.VIP, 2, "100.00"), projection(Zone.BASIC, 9, "30.00"));

        EventAvailabilityResponseDto result = eventService.availability(100L, 10);

        assertThat(result.getStatus()).isEqualTo(AvailabilityStatus.INSUFFICIENT);
    }

    @Test
    void availability_shouldNotReturnInsufficientWhenPartyEqualsZoneSeats() {
        // A party of 6 fits the 9-seat zone exactly.
        stubEvent(100L, 150);
        stubZones(projection(Zone.VIP, 2, "100.00"), projection(Zone.BASIC, 9, "30.00"));

        EventAvailabilityResponseDto result = eventService.availability(100L, 6);

        assertThat(result.getStatus()).isEqualTo(AvailabilityStatus.FEW_LEFT);
    }

    @Test
    void availability_shouldReturnAvailableWhenPartyFitsAZone() {
        stubEvent(100L, 150);
        stubZones(projection(Zone.BASIC, 9, "30.00"), projection(Zone.VIP, 20, "100.00"));

        EventAvailabilityResponseDto result = eventService.availability(100L, 2);

        assertThat(result.getStatus()).isEqualTo(AvailabilityStatus.AVAILABLE);
    }

    @Test
    void availability_shouldReturnFewLeftWhenEveryZoneIsNearlyEmpty() {
        // Party 4 fits the 8-seat zone, but each zone is below max(10, party*3).
        stubEvent(100L, 150);
        stubZones(projection(Zone.BASIC, 8, "30.00"), projection(Zone.VIP, 3, "100.00"));

        EventAvailabilityResponseDto result = eventService.availability(100L, 4);

        assertThat(result.getStatus()).isEqualTo(AvailabilityStatus.FEW_LEFT);
    }

    @Test
    void availability_shouldTreatPartyZeroAsAnyPartySize() {
        stubEvent(100L, 150);
        stubZones(projection(Zone.BASIC, 10, "30.00"));

        EventAvailabilityResponseDto result = eventService.availability(100L, 0);

        assertThat(result.getStatus()).isEqualTo(AvailabilityStatus.AVAILABLE);
    }

    @Test
    void availability_shouldClampNegativePartyToZero() {
        stubEvent(100L, 150);
        stubZones(projection(Zone.BASIC, 10, "30.00"));

        EventAvailabilityResponseDto result = eventService.availability(100L, -5);

        assertThat(result.getStatus()).isEqualTo(AvailabilityStatus.AVAILABLE);
    }

    @Test
    void availability_shouldClampPartyAtNineHundredNinetyNine() {
        // 1200 seats: an unclamped party of 5000 would be INSUFFICIENT, while
        // the clamped party of 999 fits the zone and only trips the few-left bar.
        stubEvent(100L, 1500);
        stubZones(projection(Zone.BASIC, 1200, "30.00"));

        EventAvailabilityResponseDto result = eventService.availability(100L, 5000);

        assertThat(result.getStatus()).isEqualTo(AvailabilityStatus.FEW_LEFT);
    }

    @Test
    void availability_shouldSortZonesByMinPriceThenZone() {
        stubEvent(100L, 150);
        stubZones(
                projection(Zone.FAN_ZONE, 50, "100.00"),
                projection(Zone.BASIC, 50, "50.00"),
                projection(Zone.VIP, 50, "50.00"));

        EventAvailabilityResponseDto result = eventService.availability(100L, 1);

        assertThat(result.getZones()).extracting(ZoneAvailabilityDto::getZone)
                .containsExactly(Zone.VIP, Zone.BASIC, Zone.FAN_ZONE);
        assertThat(result.getZones()).extracting(ZoneAvailabilityDto::getMinPrice)
                .containsExactly(new BigDecimal("50.00"), new BigDecimal("50.00"), new BigDecimal("100.00"));
    }

    @Test
    void availability_shouldReturnNullCapacityWhenEventHasNoVenue() {
        Event event = Event.builder().id(100L).title("Rock Concert").build();
        when(eventRepository.findById(100L)).thenReturn(Optional.of(event));
        when(ticketRepository.aggregateActiveByZone(100L)).thenReturn(List.of());

        EventAvailabilityResponseDto result = eventService.availability(100L, 0);

        assertThat(result.getCapacity()).isNull();
        assertThat(result.getStatus()).isEqualTo(AvailabilityStatus.SOLD_OUT);
    }

    @Test
    void availability_shouldThrowNotFoundWhenEventIsMissing() {
        when(eventRepository.findById(404L)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> eventService.availability(404L, 2))
                .isInstanceOf(NotFoundException.class)
                .hasMessage("Event not found");

        verify(eventRepository).findById(404L);
        verifyNoInteractions(ticketRepository);
    }

    private void stubEvent(Long eventId, Integer capacity) {
        Venue venue = Venue.builder().id(10L).place("Main Hall").capacity(capacity).build();
        Event event = Event.builder().id(eventId).title("Rock Concert").venue(venue).build();
        when(eventRepository.findById(eventId)).thenReturn(Optional.of(event));
    }

    private void stubZones(ZoneAvailabilityProjection... projections) {
        when(ticketRepository.aggregateActiveByZone(100L)).thenReturn(List.of(projections));
    }

    private ZoneAvailabilityProjection projection(Zone zone, long seatsLeft, String minPrice) {
        ZoneAvailabilityProjection projection = mock(ZoneAvailabilityProjection.class);
        when(projection.getZone()).thenReturn(zone);
        when(projection.getSeatsLeft()).thenReturn(seatsLeft);
        when(projection.getMinPrice()).thenReturn(new BigDecimal(minPrice));
        return projection;
    }
}
