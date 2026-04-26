package com.microservices_example_app.booking;

import com.microservices_example_app.booking.dto.EventCreateRequestDto;
import com.microservices_example_app.booking.dto.EventDeleteRequestDto;
import com.microservices_example_app.booking.dto.EventResponseDto;
import com.microservices_example_app.booking.dto.EventSearchRequestDto;
import com.microservices_example_app.booking.dto.EventUpdateRequestDto;
import com.microservices_example_app.booking.exceptions.NotFoundException;
import com.microservices_example_app.booking.model.Event;
import com.microservices_example_app.booking.model.EventAdmissionMode;
import com.microservices_example_app.booking.model.Venue;
import com.microservices_example_app.booking.repository.EventRepository;
import com.microservices_example_app.booking.repository.VenueRepository;
import com.microservices_example_app.booking.service.EventService;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.domain.Specification;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

@ExtendWith(org.mockito.junit.jupiter.MockitoExtension.class)
class EventServiceTest {

    @Mock
    private EventRepository eventRepository;

    @Mock
    private VenueRepository venueRepository;

    @InjectMocks
    private EventService eventService;

    @Test
    void create_shouldCreateEvent() {
        EventCreateRequestDto request = new EventCreateRequestDto();
        request.setTitle("Rock Concert");
        request.setStartsAt(LocalDateTime.of(2026, 5, 1, 19, 0));
        request.setEndsAt(LocalDateTime.of(2026, 5, 1, 22, 0));
        request.setVenueId(10);
        request.setAdmissionMode(EventAdmissionMode.GENERAL);

        Venue venue = Venue.builder()
                .id(10)
                .place("Main Hall")
                .build();

        Event saved = Event.builder()
                .id(100)
                .title("Rock Concert")
                .startsAt(LocalDateTime.of(2026, 5, 1, 19, 0))
                .endsAt(LocalDateTime.of(2026, 5, 1, 22, 0))
                .venue(venue)
                .admissionMode(EventAdmissionMode.GENERAL)
                .build();

        when(venueRepository.findById(10)).thenReturn(Optional.of(venue));
        when(eventRepository.save(any(Event.class))).thenReturn(saved);

        EventResponseDto result = eventService.create(request);

        assertThat(result).isNotNull();
        assertThat(result.getId()).isEqualTo(100);
        assertThat(result.getTitle()).isEqualTo("Rock Concert");
        assertThat(result.getVenueId()).isEqualTo(10);
        assertThat(result.getVenuePlace()).isEqualTo("Main Hall");
        assertThat(result.getAdmissionMode()).isEqualTo(EventAdmissionMode.GENERAL);

        ArgumentCaptor<Event> captor = ArgumentCaptor.forClass(Event.class);
        verify(eventRepository).save(captor.capture());

        Event actual = captor.getValue();
        assertThat(actual.getTitle()).isEqualTo("Rock Concert");
        assertThat(actual.getVenue().getId()).isEqualTo(10);
        assertThat(actual.getAdmissionMode()).isEqualTo(EventAdmissionMode.GENERAL);
        assertThat(actual.getStartsAt()).isEqualTo(LocalDateTime.of(2026, 5, 1, 19, 0));
        assertThat(actual.getEndsAt()).isEqualTo(LocalDateTime.of(2026, 5, 1, 22, 0));
    }

    @Test
    void create_shouldThrowWhenVenueNotFound() {
        EventCreateRequestDto request = new EventCreateRequestDto();
        request.setVenueId(10);

        when(venueRepository.findById(10)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> eventService.create(request))
                .isInstanceOf(NotFoundException.class)
                .hasMessage("Venue not found");

        verify(eventRepository, never()).save(any());
    }

    @Test
    void getById_shouldReturnEvent() {
        Venue venue = Venue.builder()
                .id(10)
                .place("Main Hall")
                .build();

        Event event = Event.builder()
                .id(100)
                .title("Rock Concert")
                .startsAt(LocalDateTime.of(2026, 5, 1, 19, 0))
                .endsAt(LocalDateTime.of(2026, 5, 1, 22, 0))
                .venue(venue)
                .admissionMode(EventAdmissionMode.GENERAL)
                .build();

        when(eventRepository.findById(100)).thenReturn(Optional.of(event));

        EventResponseDto result = eventService.getById(100);

        assertThat(result.getId()).isEqualTo(100);
        assertThat(result.getTitle()).isEqualTo("Rock Concert");
        assertThat(result.getVenueId()).isEqualTo(10);
        assertThat(result.getAdmissionMode()).isEqualTo(EventAdmissionMode.GENERAL);
    }

    @Test
    void getById_shouldThrowWhenEventNotFound() {
        when(eventRepository.findById(100)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> eventService.getById(100))
                .isInstanceOf(NotFoundException.class)
                .hasMessage("Event not found");
    }

    @Test
    void getAll_shouldReturnAllEvents() {
        Venue venue = Venue.builder()
                .id(10)
                .place("Main Hall")
                .build();

        Event event1 = Event.builder()
                .id(100)
                .title("Rock Concert")
                .startsAt(LocalDateTime.of(2026, 5, 1, 19, 0))
                .endsAt(LocalDateTime.of(2026, 5, 1, 22, 0))
                .venue(venue)
                .admissionMode(EventAdmissionMode.GENERAL)
                .build();

        Event event2 = Event.builder()
                .id(101)
                .title("Jazz Night")
                .startsAt(LocalDateTime.of(2026, 5, 2, 19, 0))
                .endsAt(LocalDateTime.of(2026, 5, 2, 22, 0))
                .venue(venue)
                .admissionMode(EventAdmissionMode.SEATABLE)
                .build();

        when(eventRepository.findAll()).thenReturn(List.of(event1, event2));

        List<EventResponseDto> result = eventService.getAll();

        assertThat(result).hasSize(2);
        assertThat(result.getFirst().getTitle()).isEqualTo("Rock Concert");
        assertThat(result.get(1).getTitle()).isEqualTo("Jazz Night");
    }

    @Test
    void searchByFilter_shouldReturnEvents() {
        EventSearchRequestDto filter = new EventSearchRequestDto();
        filter.setTitle("Rock");
        filter.setVenueId(10);
        filter.setAdmissionMode(EventAdmissionMode.GENERAL);
        filter.setStartsFrom(LocalDateTime.of(2026, 5, 1, 0, 0));
        filter.setStartsTo(LocalDateTime.of(2026, 5, 31, 23, 59));

        Venue venue = Venue.builder()
                .id(10)
                .place("Main Hall")
                .build();

        Event event = Event.builder()
                .id(100)
                .title("Rock Concert")
                .startsAt(LocalDateTime.of(2026, 5, 1, 19, 0))
                .endsAt(LocalDateTime.of(2026, 5, 1, 22, 0))
                .venue(venue)
                .admissionMode(EventAdmissionMode.GENERAL)
                .build();

        when(eventRepository.findAll(any(Specification.class), any(Pageable.class)))
                .thenReturn(new PageImpl<>(List.of(event)));

        List<EventResponseDto> result = eventService.searchByFilter(filter, 1, 10);

        assertThat(result).hasSize(1);
        assertThat(result.getFirst().getId()).isEqualTo(100);
        assertThat(result.getFirst().getTitle()).isEqualTo("Rock Concert");

        verify(eventRepository).findAll(any(Specification.class), any(Pageable.class));
    }

    @Test
    void searchByFilter_shouldThrowWhenPageLessThanOne() {
        EventSearchRequestDto filter = new EventSearchRequestDto();

        assertThatThrownBy(() -> eventService.searchByFilter(filter, 0, 10))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("Page must be >= 1");
    }

    @Test
    void searchByFilter_shouldThrowWhenSizeLessThanOne() {
        EventSearchRequestDto filter = new EventSearchRequestDto();

        assertThatThrownBy(() -> eventService.searchByFilter(filter, 1, 0))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("Size must be >= 1");
    }

    @Test
    void deleteById_shouldDeleteEvent() {
        when(eventRepository.existsById(100)).thenReturn(true);

        eventService.deleteById(100);

        verify(eventRepository).existsById(100);
        verify(eventRepository).deleteById(100);
    }

    @Test
    void deleteById_shouldThrowWhenIdInvalid() {
        assertThatThrownBy(() -> eventService.deleteById(0))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("Event id must be positive");

        verify(eventRepository, never()).existsById(anyInt());
        verify(eventRepository, never()).deleteById(anyInt());
    }

    @Test
    void deleteById_shouldThrowWhenEventNotFound() {
        when(eventRepository.existsById(100)).thenReturn(false);

        assertThatThrownBy(() -> eventService.deleteById(100))
                .isInstanceOf(NotFoundException.class)
                .hasMessage("Event not found");

        verify(eventRepository).existsById(100);
        verify(eventRepository, never()).deleteById(anyInt());
    }

    @Test
    void deleteByFilter_shouldDeleteMatchedEventsAndReturnCount() {
        EventDeleteRequestDto request = new EventDeleteRequestDto();
        request.setTitle("Rock Concert");
        request.setVenueId(10);
        request.setAdmissionMode(EventAdmissionMode.GENERAL);
        request.setStartsAt(LocalDateTime.of(2026, 5, 1, 19, 0));

        Venue venue = Venue.builder()
                .id(10)
                .place("Main Hall")
                .build();

        Event event1 = Event.builder()
                .id(100)
                .title("Rock Concert")
                .startsAt(LocalDateTime.of(2026, 5, 1, 19, 0))
                .endsAt(LocalDateTime.of(2026, 5, 1, 22, 0))
                .venue(venue)
                .admissionMode(EventAdmissionMode.GENERAL)
                .build();

        Event event2 = Event.builder()
                .id(101)
                .title("Rock Concert")
                .startsAt(LocalDateTime.of(2026, 5, 1, 19, 0))
                .endsAt(LocalDateTime.of(2026, 5, 1, 21, 0))
                .venue(venue)
                .admissionMode(EventAdmissionMode.GENERAL)
                .build();

        when(eventRepository.findAll(any(Specification.class)))
                .thenReturn(List.of(event1, event2));

        long result = eventService.deleteByFilter(request);

        assertThat(result).isEqualTo(2);
        verify(eventRepository).findAll(any(Specification.class));
        verify(eventRepository).deleteAll(List.of(event1, event2));
    }

    @Test
    void updateEventById_shouldUpdateEvent() {
        EventUpdateRequestDto request = new EventUpdateRequestDto();
        request.setId(100);
        request.setTitle("Updated Concert");
        request.setStartsAt(LocalDateTime.of(2026, 6, 1, 19, 0));
        request.setEndsAt(LocalDateTime.of(2026, 6, 1, 22, 30));
        request.setVenueId(11);
        request.setAdmissionMode(EventAdmissionMode.SEATABLE);

        Venue oldVenue = Venue.builder()
                .id(10)
                .place("Old Hall")
                .build();

        Venue newVenue = Venue.builder()
                .id(11)
                .place("New Hall")
                .build();

        Event existing = Event.builder()
                .id(100)
                .title("Rock Concert")
                .startsAt(LocalDateTime.of(2026, 5, 1, 19, 0))
                .endsAt(LocalDateTime.of(2026, 5, 1, 22, 0))
                .venue(oldVenue)
                .admissionMode(EventAdmissionMode.GENERAL)
                .build();

        Event updated = Event.builder()
                .id(100)
                .title("Updated Concert")
                .startsAt(LocalDateTime.of(2026, 6, 1, 19, 0))
                .endsAt(LocalDateTime.of(2026, 6, 1, 22, 30))
                .venue(newVenue)
                .admissionMode(EventAdmissionMode.SEATABLE)
                .build();

        when(eventRepository.findById(100)).thenReturn(Optional.of(existing));
        when(venueRepository.findById(11)).thenReturn(Optional.of(newVenue));
        when(eventRepository.save(any(Event.class))).thenReturn(updated);

        EventResponseDto result = eventService.updateEventById(request);

        assertThat(result.getId()).isEqualTo(100);
        assertThat(result.getTitle()).isEqualTo("Updated Concert");
        assertThat(result.getVenueId()).isEqualTo(11);
        assertThat(result.getVenuePlace()).isEqualTo("New Hall");
        assertThat(result.getAdmissionMode()).isEqualTo(EventAdmissionMode.SEATABLE);

        ArgumentCaptor<Event> captor = ArgumentCaptor.forClass(Event.class);
        verify(eventRepository).save(captor.capture());

        Event actual = captor.getValue();
        assertThat(actual.getId()).isEqualTo(100);
        assertThat(actual.getTitle()).isEqualTo("Updated Concert");
        assertThat(actual.getVenue().getId()).isEqualTo(11);
        assertThat(actual.getAdmissionMode()).isEqualTo(EventAdmissionMode.SEATABLE);
        assertThat(actual.getStartsAt()).isEqualTo(LocalDateTime.of(2026, 6, 1, 19, 0));
        assertThat(actual.getEndsAt()).isEqualTo(LocalDateTime.of(2026, 6, 1, 22, 30));
    }

    @Test
    void updateEventById_shouldThrowWhenEventNotFound() {
        EventUpdateRequestDto request = new EventUpdateRequestDto();
        request.setId(100);

        when(eventRepository.findById(100)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> eventService.updateEventById(request))
                .isInstanceOf(NotFoundException.class)
                .hasMessage("No event with id=100");

        verify(eventRepository, never()).save(any());
    }

    @Test
    void updateEventById_shouldThrowWhenVenueNotFound() {
        EventUpdateRequestDto request = new EventUpdateRequestDto();
        request.setId(100);
        request.setVenueId(11);

        Venue oldVenue = Venue.builder()
                .id(10)
                .place("Old Hall")
                .build();

        Event existing = Event.builder()
                .id(100)
                .title("Rock Concert")
                .startsAt(LocalDateTime.of(2026, 5, 1, 19, 0))
                .endsAt(LocalDateTime.of(2026, 5, 1, 22, 0))
                .venue(oldVenue)
                .admissionMode(EventAdmissionMode.GENERAL)
                .build();

        when(eventRepository.findById(100)).thenReturn(Optional.of(existing));
        when(venueRepository.findById(11)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> eventService.updateEventById(request))
                .isInstanceOf(NotFoundException.class)
                .hasMessage("Venue not found: 11");

        verify(eventRepository, never()).save(any());
    }
}