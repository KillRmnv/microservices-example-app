package com.microservices_example_app.booking;

import com.microservices_example_app.booking.dto.SeatableTicketCreateRequestDto;
import com.microservices_example_app.booking.dto.SeatableTicketDeleteRequestDto;
import com.microservices_example_app.booking.dto.SeatableTicketResponseDto;
import com.microservices_example_app.booking.dto.SeatableTicketSearchRequestDto;
import com.microservices_example_app.booking.dto.SeatableTicketUpdateRequestDto;
import com.microservices_example_app.booking.event.SuccessfulBookingEvent;
import com.microservices_example_app.booking.event.SuccessfulTicketRefundEvent;
import com.microservices_example_app.booking.exceptions.NotFoundException;
import com.microservices_example_app.booking.model.Event;
import com.microservices_example_app.booking.model.EventAdmissionMode;
import com.microservices_example_app.booking.model.Seat;
import com.microservices_example_app.booking.model.SeatableTicket;
import com.microservices_example_app.booking.model.Zone;
import com.microservices_example_app.booking.producers.NotificationKafkaBookingProducer;
import com.microservices_example_app.booking.repository.EventRepository;
import com.microservices_example_app.booking.repository.SeatRepository;
import com.microservices_example_app.booking.repository.SeatableTicketRepository;
import com.microservices_example_app.booking.service.SeatableTicketService;
import com.microservices_example_app.booking.utils.JwtRequestUserExtractor;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.test.util.ReflectionTestUtils;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

@ExtendWith(org.mockito.junit.jupiter.MockitoExtension.class)
class SeatableTicketServiceTest {

    @Mock
    private SeatableTicketRepository seatableTicketRepository;

    @Mock
    private EventRepository eventRepository;

    @Mock
    private SeatRepository seatRepository;

    @Mock
    private NotificationKafkaBookingProducer notificationKafkaBookingProducer;

    @Mock
    private JwtRequestUserExtractor jwtRequestUserExtractor;

    @InjectMocks
    private SeatableTicketService seatableTicketService;

    @BeforeEach
    void setUp() {
        ReflectionTestUtils.setField(seatableTicketService, "serviceName", "booking-service");
    }

    @Test
    void create_shouldCreateSeatableTicketAndSendBookingEvent() {
        SeatableTicketCreateRequestDto request = new SeatableTicketCreateRequestDto();
        request.setEventId(10);
        request.setSeatId(5);
        request.setZone(Zone.VIP);
        request.setPrice(BigDecimal.valueOf(250));
        request.setActive(true);
        request.setUserId(999);

        Event event = Event.builder()
                .id(10)
                .title("Rock Concert")
                .startsAt(LocalDateTime.now().plusDays(1))
                .endsAt(LocalDateTime.now().plusDays(1).plusHours(2))
                .admissionMode(EventAdmissionMode.GENERAL)
                .build();

        Seat seat = Seat.builder()
                .id(5)
                .sector("A")
                .row("3")
                .number("12")
                .build();

        SeatableTicket saved = SeatableTicket.builder()
                .id(100)
                .event(event)
                .seat(seat)
                .zone(Zone.VIP)
                .price(BigDecimal.valueOf(250))
                .active(true)
                .userId(77)
                .build();

        when(eventRepository.findById(10)).thenReturn(Optional.of(event));
        when(seatRepository.findById(5)).thenReturn(Optional.of(seat));
        when(jwtRequestUserExtractor.extractUserId()).thenReturn(77);
        when(jwtRequestUserExtractor.extractEmail()).thenReturn("test@mail.com");
        when(jwtRequestUserExtractor.extractUsername()).thenReturn("alex");
        when(seatableTicketRepository.save(any(SeatableTicket.class))).thenReturn(saved);

        SeatableTicketResponseDto result = seatableTicketService.create(request);

        assertThat(result).isNotNull();
        assertThat(result.getId()).isEqualTo(100);
        assertThat(result.getEventId()).isEqualTo(10);
        assertThat(result.getSeatId()).isEqualTo(5);
        assertThat(result.getUserId()).isEqualTo(77);
        assertThat(result.getSector()).isEqualTo("A");
        assertThat(result.getRow()).isEqualTo("3");
        assertThat(result.getNumber()).isEqualTo("12");

        ArgumentCaptor<SeatableTicket> captor = ArgumentCaptor.forClass(SeatableTicket.class);
        verify(seatableTicketRepository).save(captor.capture());

        SeatableTicket actual = captor.getValue();
        assertThat(actual.getEvent().getId()).isEqualTo(10);
        assertThat(actual.getSeat().getId()).isEqualTo(5);
        assertThat(actual.getZone()).isEqualTo(Zone.VIP);
        assertThat(actual.getPrice()).isEqualByComparingTo("250");
        assertThat(actual.isActive()).isTrue();
        assertThat(actual.getUserId()).isEqualTo(77);

        verify(notificationKafkaBookingProducer).sendSuccessfulBookingEvent(any(SuccessfulBookingEvent.class));
    }

    @Test
    void create_shouldThrowWhenEventNotFound() {
        SeatableTicketCreateRequestDto request = new SeatableTicketCreateRequestDto();
        request.setEventId(10);
        request.setSeatId(5);

        when(eventRepository.findById(10)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> seatableTicketService.create(request))
                .isInstanceOf(NotFoundException.class)
                .hasMessage("Event not found");

        verify(seatRepository, never()).findById(anyInt());
        verify(seatableTicketRepository, never()).save(any());
        verify(notificationKafkaBookingProducer, never()).sendSuccessfulBookingEvent(any());
    }

    @Test
    void create_shouldThrowWhenSeatNotFound() {
        SeatableTicketCreateRequestDto request = new SeatableTicketCreateRequestDto();
        request.setEventId(10);
        request.setSeatId(5);

        Event event = Event.builder()
                .id(10)
                .title("Rock Concert")
                .build();

        when(eventRepository.findById(10)).thenReturn(Optional.of(event));
        when(seatRepository.findById(5)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> seatableTicketService.create(request))
                .isInstanceOf(NotFoundException.class)
                .hasMessage("Seat not found");

        verify(seatableTicketRepository, never()).save(any());
        verify(notificationKafkaBookingProducer, never()).sendSuccessfulBookingEvent(any());
    }

    @Test
    void deleteById_shouldDeleteOwnSeatableTicketAndSendRefundEvent() {
        Event event = Event.builder()
                .id(10)
                .title("Rock Concert")
                .build();

        Seat seat = Seat.builder()
                .id(5)
                .sector("A")
                .row("3")
                .number("12")
                .build();

        SeatableTicket ticket = SeatableTicket.builder()
                .id(100)
                .event(event)
                .seat(seat)
                .userId(77)
                .zone(Zone.VIP)
                .price(BigDecimal.valueOf(200))
                .active(true)
                .build();

        when(seatableTicketRepository.findById(100)).thenReturn(Optional.of(ticket));
        when(jwtRequestUserExtractor.extractUserId()).thenReturn(77);
        when(jwtRequestUserExtractor.extractEmail()).thenReturn("test@mail.com");
        when(jwtRequestUserExtractor.extractUsername()).thenReturn("alex");

        seatableTicketService.deleteById(100);

        verify(seatableTicketRepository).delete(ticket);
        verify(notificationKafkaBookingProducer).sendSuccessfulTicketRefundEvent(any(SuccessfulTicketRefundEvent.class));
    }

    @Test
    void deleteById_shouldThrowWhenTicketNotFound() {
        when(seatableTicketRepository.findById(100)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> seatableTicketService.deleteById(100))
                .isInstanceOf(NotFoundException.class)
                .hasMessage("Seatable ticket not found");

        verify(seatableTicketRepository, never()).delete(any(SeatableTicket.class));
        verify(notificationKafkaBookingProducer, never()).sendSuccessfulTicketRefundEvent(any());
    }

    @Test
    void deleteById_shouldThrowWhenDeletingForeignTicket() {
        Event event = Event.builder()
                .id(10)
                .title("Rock Concert")
                .build();

        Seat seat = Seat.builder()
                .id(5)
                .sector("A")
                .row("3")
                .number("12")
                .build();

        SeatableTicket ticket = SeatableTicket.builder()
                .id(100)
                .event(event)
                .seat(seat)
                .userId(88)
                .zone(Zone.VIP)
                .build();

        when(seatableTicketRepository.findById(100)).thenReturn(Optional.of(ticket));
        when(jwtRequestUserExtractor.extractUserId()).thenReturn(77);
        when(jwtRequestUserExtractor.extractEmail()).thenReturn("test@mail.com");
        when(jwtRequestUserExtractor.extractUsername()).thenReturn("alex");

        assertThatThrownBy(() -> seatableTicketService.deleteById(100))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("You can delete only your own seatable ticket");

        verify(seatableTicketRepository, never()).delete(any(SeatableTicket.class));
        verify(notificationKafkaBookingProducer, never()).sendSuccessfulTicketRefundEvent(any());
    }

    @Test
    void updateSeatableTicketById_shouldUpdateTicketButKeepOriginalUserId() {
        SeatableTicketUpdateRequestDto request = new SeatableTicketUpdateRequestDto();
        request.setId(100);
        request.setZone(Zone.FAN_ZONE);
        request.setPrice(BigDecimal.valueOf(300));
        request.setUserId(999);

        Event event = Event.builder()
                .id(10)
                .title("Rock Concert")
                .build();

        Seat seat = Seat.builder()
                .id(5)
                .sector("A")
                .row("3")
                .number("12")
                .build();

        SeatableTicket existing = SeatableTicket.builder()
                .id(100)
                .event(event)
                .seat(seat)
                .zone(Zone.VIP)
                .price(BigDecimal.valueOf(100))
                .active(true)
                .userId(77)
                .build();

        SeatableTicket updated = SeatableTicket.builder()
                .id(100)
                .event(event)
                .seat(seat)
                .zone(Zone.FAN_ZONE)
                .price(BigDecimal.valueOf(300))
                .active(true)
                .userId(77)
                .build();

        when(seatableTicketRepository.findById(100)).thenReturn(Optional.of(existing));
        when(seatableTicketRepository.save(any(SeatableTicket.class))).thenReturn(updated);

        SeatableTicketResponseDto result = seatableTicketService.updateSeatableTicketById(request);

        assertThat(result.getId()).isEqualTo(100);
        assertThat(result.getZone()).isEqualTo(Zone.FAN_ZONE);
        assertThat(result.getPrice()).isEqualByComparingTo("300");
        assertThat(result.getUserId()).isEqualTo(77);

        ArgumentCaptor<SeatableTicket> captor = ArgumentCaptor.forClass(SeatableTicket.class);
        verify(seatableTicketRepository).save(captor.capture());
        assertThat(captor.getValue().getUserId()).isEqualTo(77);
    }

    @Test
    void searchByFilter_shouldUseCurrentUserIdFromJwt() {
        SeatableTicketSearchRequestDto filter = new SeatableTicketSearchRequestDto();
        filter.setEventId(10);
        filter.setSector("A");
        filter.setUserId(77);

        Event event = Event.builder()
                .id(10)
                .title("Rock Concert")
                .build();

        Seat seat = Seat.builder()
                .id(5)
                .sector("A")
                .row("3")
                .number("12")
                .build();

        SeatableTicket ticket = SeatableTicket.builder()
                .id(100)
                .event(event)
                .seat(seat)
                .zone(Zone.VIP)
                .price(BigDecimal.valueOf(120))
                .active(true)
                .userId(77)
                .build();

        when(seatableTicketRepository.findAll(any(Specification.class), any(Pageable.class)))
                .thenReturn(new PageImpl<>(List.of(ticket)));

        List<SeatableTicketResponseDto> result = seatableTicketService.searchByFilter(filter, 1, 10);

        assertThat(result).hasSize(1);
        assertThat(result.getFirst().getUserId()).isEqualTo(77);
        assertThat(result.getFirst().getSeatId()).isEqualTo(5);

        verify(seatableTicketRepository).findAll(any(Specification.class), any(Pageable.class));
    }

    @Test
    void searchByFilter_shouldThrowWhenPageIsLessThanOne() {
        SeatableTicketSearchRequestDto filter = new SeatableTicketSearchRequestDto();

        assertThatThrownBy(() -> seatableTicketService.searchByFilter(filter, 0, 10))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("Page must be >= 1");
    }

    @Test
    void searchByFilter_shouldThrowWhenSizeIsLessThanOne() {
        SeatableTicketSearchRequestDto filter = new SeatableTicketSearchRequestDto();

        assertThatThrownBy(() -> seatableTicketService.searchByFilter(filter, 1, 0))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("Size must be >= 1");
    }

    @Test
    void getById_shouldReturnSeatableTicket() {
        Event event = Event.builder().id(10).title("Rock Concert").build();
        Seat seat = Seat.builder().id(5).sector("A").row("3").number("12").build();
        SeatableTicket ticket = SeatableTicket.builder().id(100).event(event).seat(seat).zone(Zone.VIP).price(BigDecimal.valueOf(200)).active(true).userId(77).build();
        when(seatableTicketRepository.findById(100)).thenReturn(Optional.of(ticket));
        SeatableTicketResponseDto result = seatableTicketService.getById(100);
        assertThat(result.getId()).isEqualTo(100);
        assertThat(result.getEventId()).isEqualTo(10);
        assertThat(result.getSeatId()).isEqualTo(5);
    }

    @Test
    void getById_shouldThrowWhenTicketNotFound() {
        when(seatableTicketRepository.findById(100)).thenReturn(Optional.empty());
        assertThatThrownBy(() -> seatableTicketService.getById(100))
                .isInstanceOf(NotFoundException.class)
                .hasMessage("Seatable ticket not found");
    }

    @Test
    void refund_shouldRefundOwnActiveSeatableTicket() {
        Event event = Event.builder().id(10).title("Rock Concert").build();
        Seat seat = Seat.builder().id(5).sector("A").row("3").number("12").build();
        SeatableTicket ticket = SeatableTicket.builder().id(100).event(event).seat(seat).zone(Zone.VIP).price(BigDecimal.valueOf(200)).active(true).userId(77).build();
        when(seatableTicketRepository.findById(100)).thenReturn(Optional.of(ticket));
        when(jwtRequestUserExtractor.extractUserId()).thenReturn(77);
        when(jwtRequestUserExtractor.extractEmail()).thenReturn("test@mail.com");
        when(jwtRequestUserExtractor.extractUsername()).thenReturn("alex");
        when(seatableTicketRepository.save(any(SeatableTicket.class))).thenReturn(ticket);
        SeatableTicketResponseDto result = seatableTicketService.refund(100);
        assertThat(result).isNotNull();
        verify(notificationKafkaBookingProducer).sendSuccessfulTicketRefundEvent(any());
    }

    @Test
    void refund_shouldThrowWhenTicketNotFound() {
        when(seatableTicketRepository.findById(100)).thenReturn(Optional.empty());
        assertThatThrownBy(() -> seatableTicketService.refund(100))
                .isInstanceOf(NotFoundException.class)
                .hasMessage("Seatable ticket not found");
    }

    @Test
    void refund_shouldThrowWhenForeignTicket() {
        Event event = Event.builder().id(10).title("Rock Concert").build();
        Seat seat = Seat.builder().id(5).sector("A").row("3").number("12").build();
        SeatableTicket ticket = SeatableTicket.builder().id(100).event(event).seat(seat).zone(Zone.VIP).userId(88).build();
        when(seatableTicketRepository.findById(100)).thenReturn(Optional.of(ticket));
        when(jwtRequestUserExtractor.extractUserId()).thenReturn(77);
        assertThatThrownBy(() -> seatableTicketService.refund(100))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("You can refund only your own seatable ticket");
    }

    @Test
    void refund_shouldThrowWhenAlreadyInactive() {
        Event event = Event.builder().id(10).title("Rock Concert").build();
        Seat seat = Seat.builder().id(5).sector("A").row("3").number("12").build();
        SeatableTicket ticket = SeatableTicket.builder().id(100).event(event).seat(seat).zone(Zone.VIP).active(false).userId(77).build();
        when(seatableTicketRepository.findById(100)).thenReturn(Optional.of(ticket));
        when(jwtRequestUserExtractor.extractUserId()).thenReturn(77);
        assertThatThrownBy(() -> seatableTicketService.refund(100))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("Seatable ticket is already inactive");
    }

    @Test
    void refund_shouldThrowWhenIdNegative() {
        assertThatThrownBy(() -> seatableTicketService.refund(-1))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("SeatableTicket id must be positive");
    }

    @Test
    void deleteByFilter_shouldDeleteMatchedTicketsAndReturnCount() {
        SeatableTicketDeleteRequestDto request = new SeatableTicketDeleteRequestDto();
        request.setEventId(10);
        Event event = Event.builder().id(10).title("Rock Concert").build();
        Seat seat = Seat.builder().id(5).sector("A").row("3").number("12").build();
        SeatableTicket ticket = SeatableTicket.builder().id(100).event(event).seat(seat).zone(Zone.VIP).userId(77).build();
        when(jwtRequestUserExtractor.extractUserId()).thenReturn(77);
        when(jwtRequestUserExtractor.extractEmail()).thenReturn("test@mail.com");
        when(jwtRequestUserExtractor.extractUsername()).thenReturn("alex");
        when(seatableTicketRepository.findAll(any(Specification.class))).thenReturn(List.of(ticket));
        long result = seatableTicketService.deleteByFilter(request);
        assertThat(result).isEqualTo(1);
        verify(seatableTicketRepository).deleteAll(List.of(ticket));
        verify(notificationKafkaBookingProducer).sendSuccessfulTicketRefundEvent(any());
    }

    @Test
    void deleteByFilter_shouldThrowWhenUserIdNull() {
        SeatableTicketDeleteRequestDto request = new SeatableTicketDeleteRequestDto();
        when(jwtRequestUserExtractor.extractUserId()).thenReturn(null);
        assertThatThrownBy(() -> seatableTicketService.deleteByFilter(request))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("Cannot delete by filter: user ID not available from token");
    }

    @Test
    void deleteByFilter_shouldReturnZeroWhenNoMatch() {
        SeatableTicketDeleteRequestDto request = new SeatableTicketDeleteRequestDto();
        when(jwtRequestUserExtractor.extractUserId()).thenReturn(77);
        when(seatableTicketRepository.findAll(any(Specification.class))).thenReturn(List.of());
        long result = seatableTicketService.deleteByFilter(request);
        assertThat(result).isEqualTo(0);
    }

    @Test
    void updateSeatableTicketById_shouldThrowWhenIdNegative() {
        SeatableTicketUpdateRequestDto request = new SeatableTicketUpdateRequestDto();
        request.setId(-1);
        assertThatThrownBy(() -> seatableTicketService.updateSeatableTicketById(request))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("SeatableTicket id must be positive");
    }

    @Test
    void updateSeatableTicketById_shouldThrowWhenTicketNotFound() {
        SeatableTicketUpdateRequestDto request = new SeatableTicketUpdateRequestDto();
        request.setId(100);
        when(seatableTicketRepository.findById(100)).thenReturn(Optional.empty());
        assertThatThrownBy(() -> seatableTicketService.updateSeatableTicketById(request))
                .isInstanceOf(NotFoundException.class)
                .hasMessage("No seatable ticket with id=100");
    }

    @Test
    void updateSeatableTicketById_shouldThrowWhenEventNotFound() {
        SeatableTicketUpdateRequestDto request = new SeatableTicketUpdateRequestDto();
        request.setId(100);
        request.setEventId(99);
        Event event = Event.builder().id(10).title("Rock Concert").build();
        Seat seat = Seat.builder().id(5).sector("A").row("3").number("12").build();
        SeatableTicket existing = SeatableTicket.builder().id(100).event(event).seat(seat).zone(Zone.VIP).price(BigDecimal.valueOf(200)).active(true).userId(77).build();
        when(seatableTicketRepository.findById(100)).thenReturn(Optional.of(existing));
        when(eventRepository.findById(99)).thenReturn(Optional.empty());
        assertThatThrownBy(() -> seatableTicketService.updateSeatableTicketById(request))
                .isInstanceOf(NotFoundException.class)
                .hasMessage("Event not found: 99");
    }

    @Test
    void updateSeatableTicketById_shouldThrowWhenSeatNotFound() {
        SeatableTicketUpdateRequestDto request = new SeatableTicketUpdateRequestDto();
        request.setId(100);
        request.setSeatId(99);
        Event event = Event.builder().id(10).title("Rock Concert").build();
        Seat seat = Seat.builder().id(5).sector("A").row("3").number("12").build();
        SeatableTicket existing = SeatableTicket.builder().id(100).event(event).seat(seat).zone(Zone.VIP).price(BigDecimal.valueOf(200)).active(true).userId(77).build();
        when(seatableTicketRepository.findById(100)).thenReturn(Optional.of(existing));
        when(seatRepository.findById(99)).thenReturn(Optional.empty());
        assertThatThrownBy(() -> seatableTicketService.updateSeatableTicketById(request))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("Seat not found: 99");
    }

    @Test
    void updateSeatableTicketById_shouldKeepFieldsWhenNull() {
        SeatableTicketUpdateRequestDto request = new SeatableTicketUpdateRequestDto();
        request.setId(100);
        Event event = Event.builder().id(10).title("Rock Concert").build();
        Seat seat = Seat.builder().id(5).sector("A").row("3").number("12").build();
        SeatableTicket existing = SeatableTicket.builder().id(100).event(event).seat(seat).zone(Zone.VIP).price(BigDecimal.valueOf(200)).active(true).userId(77).build();
        SeatableTicket saved = SeatableTicket.builder().id(100).event(event).seat(seat).zone(Zone.VIP).price(BigDecimal.valueOf(200)).active(true).userId(77).build();
        when(seatableTicketRepository.findById(100)).thenReturn(Optional.of(existing));
        when(seatableTicketRepository.save(any(SeatableTicket.class))).thenReturn(saved);
        SeatableTicketResponseDto result = seatableTicketService.updateSeatableTicketById(request);
        assertThat(result.getZone()).isEqualTo(Zone.VIP);
        assertThat(result.getPrice()).isEqualByComparingTo("200");
        assertThat(result.getUserId()).isEqualTo(77);
    }


    @Test
    void deleteByFilter_shouldDeleteMultipleTicketsAndSendKafkaForEach() {
        SeatableTicketDeleteRequestDto request = new SeatableTicketDeleteRequestDto();
        request.setEventId(10);
        Event event = Event.builder().id(10).title("Rock Concert").build();
        Seat seat = Seat.builder().id(5).sector("A").row("3").number("12").build();
        SeatableTicket ticket1 = SeatableTicket.builder().id(100).event(event).seat(seat).zone(Zone.VIP).userId(77).build();
        SeatableTicket ticket2 = SeatableTicket.builder().id(101).event(event).seat(seat).zone(Zone.VIP).userId(77).build();
        when(jwtRequestUserExtractor.extractUserId()).thenReturn(77);
        when(jwtRequestUserExtractor.extractEmail()).thenReturn("test@mail.com");
        when(jwtRequestUserExtractor.extractUsername()).thenReturn("alex");
        when(seatableTicketRepository.findAll(any(Specification.class))).thenReturn(List.of(ticket1, ticket2));
        long result = seatableTicketService.deleteByFilter(request);
        assertThat(result).isEqualTo(2);
        verify(seatableTicketRepository).deleteAll(List.of(ticket1, ticket2));
        verify(notificationKafkaBookingProducer, times(2)).sendSuccessfulTicketRefundEvent(any());
    }

    @Test
    void deleteByFilter_shouldNotSendKafkaForTicketsWithNullUserId() {
        SeatableTicketDeleteRequestDto request = new SeatableTicketDeleteRequestDto();
        request.setEventId(10);
        Event event = Event.builder().id(10).title("Rock Concert").build();
        Seat seat = Seat.builder().id(5).sector("A").row("3").number("12").build();
        SeatableTicket ticket = SeatableTicket.builder().id(100).event(event).seat(seat).zone(Zone.VIP).userId(null).build();
        when(jwtRequestUserExtractor.extractUserId()).thenReturn(77);
        when(jwtRequestUserExtractor.extractEmail()).thenReturn("test@mail.com");
        when(jwtRequestUserExtractor.extractUsername()).thenReturn("alex");
        when(seatableTicketRepository.findAll(any(Specification.class))).thenReturn(List.of(ticket));
        long result = seatableTicketService.deleteByFilter(request);
        assertThat(result).isEqualTo(1);
        verify(notificationKafkaBookingProducer, never()).sendSuccessfulTicketRefundEvent(any());
    }
}