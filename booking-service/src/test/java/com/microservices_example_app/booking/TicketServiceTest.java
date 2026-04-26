package com.microservices_example_app.booking;

import com.microservices_example_app.booking.dto.TicketCreateRequestDto;
import com.microservices_example_app.booking.dto.TicketResponseDto;
import com.microservices_example_app.booking.dto.TicketUpdateRequestDto;
import com.microservices_example_app.booking.event.SuccessfulBookingEvent;
import com.microservices_example_app.booking.event.SuccessfulTicketRefundEvent;
import com.microservices_example_app.booking.exceptions.NotFoundException;
import com.microservices_example_app.booking.model.Event;
import com.microservices_example_app.booking.model.EventAdmissionMode;
import com.microservices_example_app.booking.model.Ticket;
import com.microservices_example_app.booking.model.Zone;
import com.microservices_example_app.booking.producers.NotificationKafkaBookingProducer;
import com.microservices_example_app.booking.repository.EventRepository;
import com.microservices_example_app.booking.repository.TicketRepository;
import com.microservices_example_app.booking.service.TicketService;
import com.microservices_example_app.booking.utils.JwtRequestUserExtractor;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.*;
import org.springframework.test.util.ReflectionTestUtils;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.Optional;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;

@ExtendWith(org.mockito.junit.jupiter.MockitoExtension.class)
class TicketServiceTest {

    @Mock
    private TicketRepository ticketRepository;

    @Mock
    private EventRepository eventRepository;

    @Mock
    private NotificationKafkaBookingProducer notificationKafkaBookingProducer;

    @Mock
    private JwtRequestUserExtractor jwtRequestUserExtractor;

    @InjectMocks
    private TicketService ticketService;

    @BeforeEach
    void setUp() {
        ReflectionTestUtils.setField(ticketService, "serviceName", "booking-service");
    }

    @Test
    void create_shouldCreateTicketAndSendBookingEvent() {
        TicketCreateRequestDto request = new TicketCreateRequestDto();
        request.setEventId(10);
        request.setZone(Zone.VIP);
        request.setPrice(BigDecimal.valueOf(150));
        request.setActive(true);
        request.setUserId(999);

        Event event = Event.builder()
                .id(10)
                .title("Rock Concert")
                .startsAt(LocalDateTime.now().plusDays(1))
                .endsAt(LocalDateTime.now().plusDays(1).plusHours(2))
                .admissionMode(EventAdmissionMode.GENERAL)
                .build();

        Ticket savedTicket = Ticket.builder()
                .id(100)
                .event(event)
                .zone(Zone.VIP)
                .price(BigDecimal.valueOf(150))
                .active(true)
                .userId(77)
                .build();

        when(eventRepository.findById(10)).thenReturn(Optional.of(event));
        when(jwtRequestUserExtractor.extractUserId()).thenReturn(77);
        when(jwtRequestUserExtractor.extractEmail()).thenReturn("test@mail.com");
        when(jwtRequestUserExtractor.extractUsername()).thenReturn("alex");
        when(ticketRepository.save(any(Ticket.class))).thenReturn(savedTicket);

        TicketResponseDto result = ticketService.create(request);

        assertThat(result).isNotNull();
        assertThat(result.getId()).isEqualTo(100);
        assertThat(result.getEventId()).isEqualTo(10);
        assertThat(result.getEventTitle()).isEqualTo("Rock Concert");
        assertThat(result.getUserId()).isEqualTo(77);

        verify(ticketRepository).save(argThat(ticket ->
                ticket.getUserId().equals(77)
                        && ticket.getEvent().getId().equals(10)
                        && ticket.getZone() == Zone.VIP
        ));

        verify(notificationKafkaBookingProducer).sendSuccessfulBookingEvent(any(SuccessfulBookingEvent.class));
    }

    @Test
    void create_shouldThrowWhenEventNotFound() {
        TicketCreateRequestDto request = new TicketCreateRequestDto();
        request.setEventId(10);

        when(eventRepository.findById(10)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> ticketService.create(request))
                .isInstanceOf(NotFoundException.class)
                .hasMessage("Event not found");

        verify(ticketRepository, never()).save(any());
        verify(notificationKafkaBookingProducer, never()).sendSuccessfulBookingEvent(any());
    }

    @Test
    void deleteById_shouldDeleteOwnTicketAndSendRefundEvent() {
        Event event = Event.builder()
                .id(10)
                .title("Rock Concert")
                .build();

        Ticket ticket = Ticket.builder()
                .id(100)
                .event(event)
                .userId(77)
                .zone(Zone.VIP)
                .price(BigDecimal.valueOf(120))
                .active(true)
                .build();

        when(ticketRepository.findById(100)).thenReturn(Optional.of(ticket));
        when(jwtRequestUserExtractor.extractUserId()).thenReturn(77);
        when(jwtRequestUserExtractor.extractEmail()).thenReturn("test@mail.com");
        when(jwtRequestUserExtractor.extractUsername()).thenReturn("alex");

        ticketService.deleteById(100);

        verify(ticketRepository).delete(ticket);
        verify(notificationKafkaBookingProducer).sendSuccessfulTicketRefundEvent(any(SuccessfulTicketRefundEvent.class));
    }

    @Test
    void deleteById_shouldThrowWhenTicketNotFound() {
        when(ticketRepository.findById(100)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> ticketService.deleteById(100))
                .isInstanceOf(NotFoundException.class)
                .hasMessage("Ticket not found");

        verify(ticketRepository, never()).delete((Ticket) any());
        verify(notificationKafkaBookingProducer, never()).sendSuccessfulTicketRefundEvent(any());
    }

    @Test
    void deleteById_shouldThrowWhenDeletingForeignTicket() {
        Event event = Event.builder()
                .id(10)
                .title("Rock Concert")
                .build();

        Ticket ticket = Ticket.builder()
                .id(100)
                .event(event)
                .userId(88)
                .build();

        when(ticketRepository.findById(100)).thenReturn(Optional.of(ticket));
        when(jwtRequestUserExtractor.extractUserId()).thenReturn(77);
        when(jwtRequestUserExtractor.extractEmail()).thenReturn("test@mail.com");
        when(jwtRequestUserExtractor.extractUsername()).thenReturn("alex");

        assertThatThrownBy(() -> ticketService.deleteById(100))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("You can delete only your own ticket");

        verify(ticketRepository, never()).delete((Ticket) any());
        verify(notificationKafkaBookingProducer, never()).sendSuccessfulTicketRefundEvent(any());
    }

    @Test
    void updateTicketById_shouldUpdateTicket() {
        TicketUpdateRequestDto request = new TicketUpdateRequestDto();
        request.setId(100);
        request.setZone(Zone.FAN_ZONE);
        request.setPrice(BigDecimal.valueOf(300));

        Event event = Event.builder()
                .id(10)
                .title("Rock Concert")
                .build();

        Ticket existing = Ticket.builder()
                .id(100)
                .event(event)
                .zone(Zone.VIP)
                .price(BigDecimal.valueOf(100))
                .active(true)
                .userId(77)
                .build();

        Ticket updated = Ticket.builder()
                .id(100)
                .event(event)
                .zone(Zone.FAN_ZONE)
                .price(BigDecimal.valueOf(300))
                .active(true)
                .userId(77)
                .build();

        when(ticketRepository.findById(100)).thenReturn(Optional.of(existing));
        when(ticketRepository.save(any(Ticket.class))).thenReturn(updated);

        TicketResponseDto result = ticketService.updateTicketById(request);

        assertThat(result.getId()).isEqualTo(100);
        assertThat(result.getZone()).isEqualTo(Zone.FAN_ZONE);
        assertThat(result.getPrice()).isEqualByComparingTo("300");
    }
}