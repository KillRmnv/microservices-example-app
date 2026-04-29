package com.microservices_example_app.booking.controller;

import com.microservices_example_app.booking.dto.*;
import com.microservices_example_app.booking.service.SeatableTicketService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/booking/seatable-tickets")
@RequiredArgsConstructor
@Slf4j
public class SeatableTicketController {

    private final SeatableTicketService seatableTicketService;

    @PostMapping
    public SeatableTicketResponseDto create(@Valid @RequestBody SeatableTicketCreateRequestDto requestDto) {
        log.info("Creating seatable ticket for event id: {}", requestDto.getEventId());
        return seatableTicketService.create(requestDto);
    }

    @GetMapping("/{id}")
    public SeatableTicketResponseDto getById(@PathVariable Integer id) {
        log.info("Fetching seatable ticket with id: {}", id);
        return seatableTicketService.getById(id);
    }

    @GetMapping("/search")
    public List<SeatableTicketResponseDto> searchByFilter(@Valid @ModelAttribute SeatableTicketSearchRequestDto filter,
                                                          @RequestParam(defaultValue = "1") int page,
                                                          @RequestParam(defaultValue = "10") int size) {
        log.info("Searching seatable tickets by filter: eventId={}, userId={}, sector={}", 
                filter.getEventId(), filter.getUserId(), filter.getSector());
        return seatableTicketService.searchByFilter(filter, page, size);
    }

    @PutMapping("/{id}")
    public SeatableTicketResponseDto updateById(@PathVariable Integer id,
                                                @Valid @RequestBody SeatableTicketUpdateRequestDto requestDto) {
        log.info("Updating seatable ticket with id: {}", id);
        requestDto.setId(id);
        return seatableTicketService.updateSeatableTicketById(requestDto);
    }

    @DeleteMapping("/{id}")
    public void deleteById(@PathVariable Integer id) {
        log.info("Deleting seatable ticket with id: {}", id);
        seatableTicketService.deleteById(id);
    }

    @DeleteMapping("/search")
    public long deleteByFilter(@Valid @RequestBody SeatableTicketDeleteRequestDto requestDto) {
        log.info("Deleting seatable tickets by filter: eventId={}, userId={}", 
                requestDto.getEventId(), requestDto.getUserId());
        return seatableTicketService.deleteByFilter(requestDto);
    }
}