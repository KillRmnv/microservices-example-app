package com.microservices_example_app.booking;

import com.microservices_example_app.booking.dto.TicketCreateRequestDto;
import com.microservices_example_app.booking.dto.TicketDeleteRequestDto;
import com.microservices_example_app.booking.dto.TicketResponseDto;
import com.microservices_example_app.booking.dto.TicketSearchRequestDto;
import com.microservices_example_app.booking.dto.TicketUpdateRequestDto;
import com.microservices_example_app.booking.event.SuccessfulBookingEvent;
import com.microservices_example_app.booking.event.SuccessfulTicketRefundEvent;
import com.microservices_example_app.booking.exceptions.NotFoundException;
import com.microservices_example_app.booking.model.Event;
import com.microservices_example_app.booking.model.EventAdmissionMode;
import com.microservices_example_app.booking.model.Ticket;
import com.microservices_example_app.booking.model.Zone;
import com.microservices_example_app.booking.producers.NotificationKafkaBookingProducer;
import com.microservices_example_app.booking.producers.NotificationKafkaUserProducer;
import com.microservices_example_app.booking.repository.EventRepository;
import com.microservices_example_app.booking.repository.TicketRepository;
import com.microservices_example_app.booking.service.TicketService;
import com.microservices_example_app.booking.utils.JwtRequestUserExtractor;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.*;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.domain.Specification;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;
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
    private NotificationKafkaUserProducer kafkaUserProducer;

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

    @Test
    void getById_shouldReturnTicket() {
        Event event = Event.builder().id(10).title("Rock Concert").build();
        Ticket ticket = Ticket.builder().id(100).event(event).zone(Zone.VIP).price(BigDecimal.valueOf(150)).active(true).userId(77).build();
        when(ticketRepository.findById(100)).thenReturn(Optional.of(ticket));
        TicketResponseDto result = ticketService.getById(100);
        assertThat(result.getId()).isEqualTo(100);
        assertThat(result.getEventId()).isEqualTo(10);
        assertThat(result.getEventTitle()).isEqualTo("Rock Concert");
        assertThat(result.getZone()).isEqualTo(Zone.VIP);
    }

    @Test
    void getById_shouldThrowWhenTicketNotFound() {
        when(ticketRepository.findById(100)).thenReturn(Optional.empty());
        assertThatThrownBy(() -> ticketService.getById(100))
                .isInstanceOf(NotFoundException.class)
                .hasMessage("Ticket not found");
    }

    @Test
    void searchByFilter_shouldReturnTickets() {
        TicketSearchRequestDto filter = new TicketSearchRequestDto();
        filter.setEventId(10);
        filter.setZone(Zone.VIP);
        Event event = Event.builder().id(10).title("Rock Concert").build();
        Ticket ticket = Ticket.builder().id(100).event(event).zone(Zone.VIP).price(BigDecimal.valueOf(150)).active(true).userId(77).build();
        when(ticketRepository.findAll(any(Specification.class), any(Pageable.class)))
                .thenReturn(new PageImpl<>(List.of(ticket)));
        List<TicketResponseDto> result = ticketService.searchByFilter(filter, 1, 10);
        assertThat(result).hasSize(1);
        assertThat(result.getFirst().getId()).isEqualTo(100);
    }

    @Test
    void searchByFilter_shouldThrowWhenPageInvalid() {
        TicketSearchRequestDto filter = new TicketSearchRequestDto();
        assertThatThrownBy(() -> ticketService.searchByFilter(filter, 0, 10))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("Page must be >= 1");
    }

    @Test
    void searchByFilter_shouldThrowWhenSizeInvalid() {
        TicketSearchRequestDto filter = new TicketSearchRequestDto();
        assertThatThrownBy(() -> ticketService.searchByFilter(filter, 1, 0))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("Size must be >= 1");
    }

    @Test
    void deleteByFilter_shouldDeleteMatchedTicketsAndReturnCount() {
        TicketDeleteRequestDto request = new TicketDeleteRequestDto();
        request.setEventId(10);
        request.setZone(Zone.VIP);
        Event event = Event.builder().id(10).title("Rock Concert").build();
        Ticket ticket = Ticket.builder().id(100).event(event).zone(Zone.VIP).userId(77).build();
        when(ticketRepository.findAll(any(Specification.class))).thenReturn(List.of(ticket));
        long result = ticketService.deleteByFilter(request);
        assertThat(result).isEqualTo(1);
        verify(ticketRepository).deleteAll(List.of(ticket));
        verify(kafkaUserProducer).sendDeleteEventEvent(any());
    }

    @Test
    void deleteByFilter_shouldReturnZeroWhenNoMatch() {
        TicketDeleteRequestDto request = new TicketDeleteRequestDto();
        when(ticketRepository.findAll(any(Specification.class))).thenReturn(List.of());
        long result = ticketService.deleteByFilter(request);
        assertThat(result).isEqualTo(0);
    }

    @Test
    void refund_shouldRefundOwnActiveTicket() {
        Event event = Event.builder().id(10).title("Rock Concert").build();
        Ticket ticket = Ticket.builder().id(100).event(event).zone(Zone.VIP).price(BigDecimal.valueOf(150)).active(true).userId(77).build();
        when(ticketRepository.findById(100)).thenReturn(Optional.of(ticket));
        when(jwtRequestUserExtractor.extractUserId()).thenReturn(77);
        when(jwtRequestUserExtractor.extractEmail()).thenReturn("test@mail.com");
        when(jwtRequestUserExtractor.extractUsername()).thenReturn("alex");
        when(ticketRepository.save(any(Ticket.class))).thenReturn(ticket);
        TicketResponseDto result = ticketService.refund(100);
        assertThat(result).isNotNull();
        verify(notificationKafkaBookingProducer).sendSuccessfulTicketRefundEvent(any());
    }

    @Test
    void refund_shouldThrowWhenTicketNotFound() {
        when(ticketRepository.findById(100)).thenReturn(Optional.empty());
        assertThatThrownBy(() -> ticketService.refund(100))
                .isInstanceOf(NotFoundException.class)
                .hasMessage("Ticket not found");
    }

    @Test
    void refund_shouldThrowWhenForeignTicket() {
        Event event = Event.builder().id(10).title("Rock Concert").build();
        Ticket ticket = Ticket.builder().id(100).event(event).zone(Zone.VIP).userId(88).build();
        when(ticketRepository.findById(100)).thenReturn(Optional.of(ticket));
        when(jwtRequestUserExtractor.extractUserId()).thenReturn(77);
        assertThatThrownBy(() -> ticketService.refund(100))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("You can refund only your own ticket");
    }

    @Test
    void refund_shouldThrowWhenTicketAlreadyInactive() {
        Event event = Event.builder().id(10).title("Rock Concert").build();
        Ticket ticket = Ticket.builder().id(100).event(event).zone(Zone.VIP).active(false).userId(77).build();
        when(ticketRepository.findById(100)).thenReturn(Optional.of(ticket));
        when(jwtRequestUserExtractor.extractUserId()).thenReturn(77);
        assertThatThrownBy(() -> ticketService.refund(100))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("Ticket is already inactive");
    }

    @Test
    void refund_shouldThrowWhenIdNegative() {
        assertThatThrownBy(() -> ticketService.refund(-1))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("Ticket id must be positive");
    }

    @Test
    void updateTicketById_shouldThrowWhenTicketNotFound() {
        TicketUpdateRequestDto request = new TicketUpdateRequestDto();
        request.setId(100);
        when(ticketRepository.findById(100)).thenReturn(Optional.empty());
        when(jwtRequestUserExtractor.extractUserId()).thenReturn(77);
        assertThatThrownBy(() -> ticketService.updateTicketById(request))
                .isInstanceOf(NotFoundException.class)
                .hasMessage("No ticket with id=100");
    }

    @Test
    void updateTicketById_shouldSendKafkaWhenUserIdChanges() {
        TicketUpdateRequestDto request = new TicketUpdateRequestDto();
        request.setId(100);
        request.setZone(Zone.FAN_ZONE);
        Event event = Event.builder().id(10).title("Rock Concert").build();
        Ticket existing = Ticket.builder().id(100).event(event).zone(Zone.VIP).price(BigDecimal.valueOf(100)).active(true).userId(77).build();
        Ticket updated = Ticket.builder().id(100).event(event).zone(Zone.FAN_ZONE).price(BigDecimal.valueOf(100)).active(true).userId(88).build();
        when(ticketRepository.findById(100)).thenReturn(Optional.of(existing));
        when(jwtRequestUserExtractor.extractUserId()).thenReturn(88);
        when(jwtRequestUserExtractor.extractEmail()).thenReturn("new@mail.com");
        when(jwtRequestUserExtractor.extractUsername()).thenReturn("newuser");
        when(ticketRepository.save(any(Ticket.class))).thenReturn(updated);
        ticketService.updateTicketById(request);
        verify(notificationKafkaBookingProducer).sendSuccessfulTicketRefundEvent(any());
        verify(notificationKafkaBookingProducer).sendSuccessfulBookingEvent(any());
    }

    @Test
    void updateTicketById_shouldThrowWhenIdNegative() {
        TicketUpdateRequestDto request = new TicketUpdateRequestDto();
        request.setId(-1);
        assertThatThrownBy(() -> ticketService.updateTicketById(request))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("Ticket id must be positive");
    }


    @Test
    void create_shouldSetActiveFalseWhenRequestActiveFalse() {
        TicketCreateRequestDto request = new TicketCreateRequestDto();
        request.setEventId(10);
        request.setZone(Zone.VIP);
        request.setPrice(BigDecimal.valueOf(150));
        request.setActive(false);
        Event event = Event.builder().id(10).title("Rock Concert").startsAt(LocalDateTime.now().plusDays(1)).endsAt(LocalDateTime.now().plusDays(1).plusHours(2)).admissionMode(EventAdmissionMode.GENERAL).build();
        Ticket savedTicket = Ticket.builder().id(100).event(event).zone(Zone.VIP).price(BigDecimal.valueOf(150)).active(false).userId(77).build();
        when(eventRepository.findById(10)).thenReturn(Optional.of(event));
        when(jwtRequestUserExtractor.extractUserId()).thenReturn(77);
        when(jwtRequestUserExtractor.extractEmail()).thenReturn("test@mail.com");
        when(jwtRequestUserExtractor.extractUsername()).thenReturn("alex");
        when(ticketRepository.save(any(Ticket.class))).thenReturn(savedTicket);
        TicketResponseDto result = ticketService.create(request);
        assertThat(result.getActive()).isFalse();
    }

    @Test
    void create_shouldSetActiveFalseWhenRequestActiveNull() {
        TicketCreateRequestDto request = new TicketCreateRequestDto();
        request.setEventId(10);
        request.setZone(Zone.VIP);
        request.setPrice(BigDecimal.valueOf(150));
        request.setActive(null);
        Event event = Event.builder().id(10).title("Rock Concert").startsAt(LocalDateTime.now().plusDays(1)).endsAt(LocalDateTime.now().plusDays(1).plusHours(2)).admissionMode(EventAdmissionMode.GENERAL).build();
        Ticket savedTicket = Ticket.builder().id(100).event(event).zone(Zone.VIP).price(BigDecimal.valueOf(150)).active(false).userId(77).build();
        when(eventRepository.findById(10)).thenReturn(Optional.of(event));
        when(jwtRequestUserExtractor.extractUserId()).thenReturn(77);
        when(jwtRequestUserExtractor.extractEmail()).thenReturn("test@mail.com");
        when(jwtRequestUserExtractor.extractUsername()).thenReturn("alex");
        when(ticketRepository.save(any(Ticket.class))).thenReturn(savedTicket);
        TicketResponseDto result = ticketService.create(request);
        assertThat(result.getActive()).isFalse();
    }


    @Test
    void deleteById_shouldThrowWhenTicketHasNoOwner() {
        Event event = Event.builder().id(10).title("Rock Concert").build();
        Ticket ticket = Ticket.builder().id(100).event(event).userId(null).zone(Zone.VIP).price(BigDecimal.valueOf(120)).active(true).build();
        when(ticketRepository.findById(100)).thenReturn(Optional.of(ticket));
        when(jwtRequestUserExtractor.extractUserId()).thenReturn(77);
        assertThatThrownBy(() -> ticketService.deleteById(100))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("You can delete only your own ticket");
        verify(ticketRepository, never()).delete(any(Ticket.class));
    }


    @Test
    void updateTicketById_shouldNotSendKafkaWhenSameUserId() {
        TicketUpdateRequestDto request = new TicketUpdateRequestDto();
        request.setId(100);
        request.setZone(Zone.FAN_ZONE);
        Event event = Event.builder().id(10).title("Rock Concert").build();
        Ticket existing = Ticket.builder().id(100).event(event).zone(Zone.VIP).price(BigDecimal.valueOf(100)).active(true).userId(77).build();
        Ticket updated = Ticket.builder().id(100).event(event).zone(Zone.FAN_ZONE).price(BigDecimal.valueOf(100)).active(true).userId(77).build();
        when(ticketRepository.findById(100)).thenReturn(Optional.of(existing));
        when(jwtRequestUserExtractor.extractUserId()).thenReturn(77);
        when(ticketRepository.save(any(Ticket.class))).thenReturn(updated);
        ticketService.updateTicketById(request);
        verify(notificationKafkaBookingProducer, never()).sendSuccessfulTicketRefundEvent(any());
        verify(notificationKafkaBookingProducer, never()).sendSuccessfulBookingEvent(any());
    }


    @Test
    void updateTicketById_shouldSendKafkaWhenPreviousUserIdIsNull() {
        TicketUpdateRequestDto request = new TicketUpdateRequestDto();
        request.setId(100);
        request.setZone(Zone.FAN_ZONE);
        Event event = Event.builder().id(10).title("Rock Concert").build();
        Ticket existing = Ticket.builder().id(100).event(event).zone(Zone.VIP).price(BigDecimal.valueOf(100)).active(true).userId(null).build();
        Ticket updated = Ticket.builder().id(100).event(event).zone(Zone.FAN_ZONE).price(BigDecimal.valueOf(100)).active(true).userId(77).build();
        when(ticketRepository.findById(100)).thenReturn(Optional.of(existing));
        when(jwtRequestUserExtractor.extractUserId()).thenReturn(77);
        when(jwtRequestUserExtractor.extractEmail()).thenReturn("test@mail.com");
        when(jwtRequestUserExtractor.extractUsername()).thenReturn("alex");
        when(ticketRepository.save(any(Ticket.class))).thenReturn(updated);
        ticketService.updateTicketById(request);
        verify(notificationKafkaBookingProducer).sendSuccessfulTicketRefundEvent(any());
        verify(notificationKafkaBookingProducer).sendSuccessfulBookingEvent(any());
    }
}