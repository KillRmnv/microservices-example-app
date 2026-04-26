package com.microservices_example_app.booking;

import com.microservices_example_app.booking.dto.SeatCreateRequestDto;
import com.microservices_example_app.booking.dto.SeatDeleteRequestDto;
import com.microservices_example_app.booking.dto.SeatResponseDto;
import com.microservices_example_app.booking.dto.SeatSearchRequestDto;
import com.microservices_example_app.booking.dto.SeatUpdateRequestDto;
import com.microservices_example_app.booking.exceptions.NotFoundException;
import com.microservices_example_app.booking.model.Seat;
import com.microservices_example_app.booking.model.Venue;
import com.microservices_example_app.booking.repository.SeatRepository;
import com.microservices_example_app.booking.repository.VenueRepository;
import com.microservices_example_app.booking.service.SeatService;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.domain.Specification;

import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

@ExtendWith(org.mockito.junit.jupiter.MockitoExtension.class)
class SeatServiceTest {

    @Mock
    private SeatRepository seatRepository;

    @Mock
    private VenueRepository venueRepository;

    @InjectMocks
    private SeatService seatService;

    @Test
    void create_shouldCreateSeat() {
        SeatCreateRequestDto request = new SeatCreateRequestDto();
        request.setVenueId(10);
        request.setSector("A");
        request.setRow("3");
        request.setNumber("12");

        Venue venue = Venue.builder()
                .id(10)
                .place("Main Hall")
                .build();

        Seat savedSeat = Seat.builder()
                .id(100)
                .sector("A")
                .row("3")
                .number("12")
                .venue(venue)
                .build();

        when(venueRepository.findById(10)).thenReturn(Optional.of(venue));
        when(seatRepository.save(any(Seat.class))).thenReturn(savedSeat);

        SeatResponseDto result = seatService.create(request);

        assertThat(result).isNotNull();
        assertThat(result.getId()).isEqualTo(100);
        assertThat(result.getSector()).isEqualTo("A");
        assertThat(result.getRow()).isEqualTo("3");
        assertThat(result.getNumber()).isEqualTo("12");
        assertThat(result.getVenueId()).isEqualTo(10);
        assertThat(result.getVenuePlace()).isEqualTo("Main Hall");

        ArgumentCaptor<Seat> captor = ArgumentCaptor.forClass(Seat.class);
        verify(seatRepository).save(captor.capture());

        Seat actual = captor.getValue();
        assertThat(actual.getSector()).isEqualTo("A");
        assertThat(actual.getRow()).isEqualTo("3");
        assertThat(actual.getNumber()).isEqualTo("12");
        assertThat(actual.getVenue().getId()).isEqualTo(10);
    }

    @Test
    void create_shouldThrowWhenVenueNotFound() {
        SeatCreateRequestDto request = new SeatCreateRequestDto();
        request.setVenueId(10);

        when(venueRepository.findById(10)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> seatService.create(request))
                .isInstanceOf(NotFoundException.class)
                .hasMessage("Venue not found");

        verify(seatRepository, never()).save(any());
    }

    @Test
    void getById_shouldReturnSeat() {
        Venue venue = Venue.builder()
                .id(10)
                .place("Main Hall")
                .build();

        Seat seat = Seat.builder()
                .id(100)
                .sector("A")
                .row("3")
                .number("12")
                .venue(venue)
                .build();

        when(seatRepository.findById(100)).thenReturn(Optional.of(seat));

        SeatResponseDto result = seatService.getById(100);

        assertThat(result.getId()).isEqualTo(100);
        assertThat(result.getSector()).isEqualTo("A");
        assertThat(result.getVenueId()).isEqualTo(10);
    }

    @Test
    void getById_shouldThrowWhenSeatNotFound() {
        when(seatRepository.findById(100)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> seatService.getById(100))
                .isInstanceOf(NotFoundException.class)
                .hasMessage("Seat not found");
    }

    @Test
    void searchByFilter_shouldReturnSeats() {
        SeatSearchRequestDto filter = new SeatSearchRequestDto();
        filter.setVenueId(10);
        filter.setSector("A");

        Venue venue = Venue.builder()
                .id(10)
                .place("Main Hall")
                .build();

        Seat seat = Seat.builder()
                .id(100)
                .sector("A")
                .row("3")
                .number("12")
                .venue(venue)
                .build();

        when(seatRepository.findAll(any(Specification.class), any(Pageable.class)))
                .thenReturn(new PageImpl<>(List.of(seat)));

        List<SeatResponseDto> result = seatService.searchByFilter(filter, 1, 10);

        assertThat(result).hasSize(1);
        assertThat(result.getFirst().getId()).isEqualTo(100);
        assertThat(result.getFirst().getVenuePlace()).isEqualTo("Main Hall");

        verify(seatRepository).findAll(any(Specification.class), any(Pageable.class));
    }

    @Test
    void searchByFilter_shouldThrowWhenPageLessThanOne() {
        SeatSearchRequestDto filter = new SeatSearchRequestDto();

        assertThatThrownBy(() -> seatService.searchByFilter(filter, 0, 10))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("Page must be >= 1");
    }

    @Test
    void searchByFilter_shouldThrowWhenSizeLessThanOne() {
        SeatSearchRequestDto filter = new SeatSearchRequestDto();

        assertThatThrownBy(() -> seatService.searchByFilter(filter, 1, 0))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("Size must be >= 1");
    }

    @Test
    void deleteById_shouldDeleteSeat() {
        when(seatRepository.existsById(100)).thenReturn(true);

        seatService.deleteById(100);

        verify(seatRepository).existsById(100);
        verify(seatRepository).deleteById(100);
    }

    @Test
    void deleteById_shouldThrowWhenIdInvalid() {
        assertThatThrownBy(() -> seatService.deleteById(0))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("Seat id must be positive");

        verify(seatRepository, never()).existsById(anyInt());
        verify(seatRepository, never()).deleteById(anyInt());
    }

    @Test
    void deleteById_shouldThrowWhenSeatNotFound() {
        when(seatRepository.existsById(100)).thenReturn(false);

        assertThatThrownBy(() -> seatService.deleteById(100))
                .isInstanceOf(NotFoundException.class)
                .hasMessage("Seat not found");

        verify(seatRepository).existsById(100);
        verify(seatRepository, never()).deleteById(anyInt());
    }

    @Test
    void deleteByFilter_shouldDeleteAllMatchedSeatsAndReturnCount() {
        SeatDeleteRequestDto request = new SeatDeleteRequestDto();
        request.setVenueId(10);
        request.setSector("A");
        request.setRow("3");
        request.setNumber("12");

        Venue venue = Venue.builder()
                .id(10)
                .place("Main Hall")
                .build();

        Seat seat1 = Seat.builder()
                .id(100)
                .sector("A")
                .row("3")
                .number("12")
                .venue(venue)
                .build();

        Seat seat2 = Seat.builder()
                .id(101)
                .sector("A")
                .row("3")
                .number("12")
                .venue(venue)
                .build();

        when(seatRepository.findAll(any(Specification.class)))
                .thenReturn(List.of(seat1, seat2));

        long result = seatService.deleteByFilter(request);

        assertThat(result).isEqualTo(2);
        verify(seatRepository).findAll(any(Specification.class));
        verify(seatRepository).deleteAll(List.of(seat1, seat2));
    }

    @Test
    void updateSeatById_shouldUpdateSeat() {
        SeatUpdateRequestDto request = new SeatUpdateRequestDto();
        request.setId(100);
        request.setSector("B");
        request.setRow("5");
        request.setNumber("20");
        request.setVenueId(11);

        Venue oldVenue = Venue.builder()
                .id(10)
                .place("Old Hall")
                .build();

        Venue newVenue = Venue.builder()
                .id(11)
                .place("New Hall")
                .build();

        Seat existing = Seat.builder()
                .id(100)
                .sector("A")
                .row("3")
                .number("12")
                .venue(oldVenue)
                .build();

        Seat updated = Seat.builder()
                .id(100)
                .sector("B")
                .row("5")
                .number("20")
                .venue(newVenue)
                .build();

        when(seatRepository.findById(100)).thenReturn(Optional.of(existing));
        when(venueRepository.findById(11)).thenReturn(Optional.of(newVenue));
        when(seatRepository.save(any(Seat.class))).thenReturn(updated);

        SeatResponseDto result = seatService.updateSeatById(request);

        assertThat(result.getId()).isEqualTo(100);
        assertThat(result.getSector()).isEqualTo("B");
        assertThat(result.getRow()).isEqualTo("5");
        assertThat(result.getNumber()).isEqualTo("20");
        assertThat(result.getVenueId()).isEqualTo(11);
        assertThat(result.getVenuePlace()).isEqualTo("New Hall");

        ArgumentCaptor<Seat> captor = ArgumentCaptor.forClass(Seat.class);
        verify(seatRepository).save(captor.capture());

        Seat actual = captor.getValue();
        assertThat(actual.getId()).isEqualTo(100);
        assertThat(actual.getSector()).isEqualTo("B");
        assertThat(actual.getRow()).isEqualTo("5");
        assertThat(actual.getNumber()).isEqualTo("20");
        assertThat(actual.getVenue().getId()).isEqualTo(11);
    }

    @Test
    void updateSeatById_shouldThrowWhenSeatNotFound() {
        SeatUpdateRequestDto request = new SeatUpdateRequestDto();
        request.setId(100);

        when(seatRepository.findById(100)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> seatService.updateSeatById(request))
                .isInstanceOf(NotFoundException.class)
                .hasMessage("No seat with id=100");

        verify(seatRepository, never()).save(any());
    }

    @Test
    void updateSeatById_shouldThrowWhenVenueNotFound() {
        SeatUpdateRequestDto request = new SeatUpdateRequestDto();
        request.setId(100);
        request.setVenueId(11);

        Venue oldVenue = Venue.builder()
                .id(10)
                .place("Old Hall")
                .build();

        Seat existing = Seat.builder()
                .id(100)
                .sector("A")
                .row("3")
                .number("12")
                .venue(oldVenue)
                .build();

        when(seatRepository.findById(100)).thenReturn(Optional.of(existing));
        when(venueRepository.findById(11)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> seatService.updateSeatById(request))
                .isInstanceOf(NotFoundException.class)
                .hasMessage("Venue not found: 11");

        verify(seatRepository, never()).save(any());
    }
}