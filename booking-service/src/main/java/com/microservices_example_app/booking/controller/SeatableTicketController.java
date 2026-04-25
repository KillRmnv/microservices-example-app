package com.microservices_example_app.booking.controller;

import com.microservices_example_app.booking.dto.*;
import com.microservices_example_app.booking.service.SeatableTicketService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/booking/seatable-tickets")
@RequiredArgsConstructor
public class SeatableTicketController {

    private final SeatableTicketService seatableTicketService;

    @PostMapping
    public SeatableTicketResponseDto create(@RequestBody SeatableTicketCreateRequestDto requestDto) {
        return seatableTicketService.create(requestDto);
    }

    @GetMapping("/{id}")
    public SeatableTicketResponseDto getById(@PathVariable Integer id) {
        return seatableTicketService.getById(id);
    }

    @GetMapping("/search")
    public List<SeatableTicketResponseDto> searchByFilter(@ModelAttribute SeatableTicketSearchRequestDto filter,
                                                          @RequestParam(defaultValue = "1") int page,
                                                          @RequestParam(defaultValue = "10") int size) {
        return seatableTicketService.searchByFilter(filter, page, size);
    }

    @PutMapping("/{id}")
    public SeatableTicketResponseDto updateById(@PathVariable Integer id,
                                                @RequestBody SeatableTicketUpdateRequestDto requestDto) {
        requestDto.setId(id);
        return seatableTicketService.updateSeatableTicketById(requestDto);
    }

    @DeleteMapping("/{id}")
    public void deleteById(@PathVariable Integer id) {
        seatableTicketService.deleteById(id);
    }

    @DeleteMapping("/search")
    public long deleteByFilter(@RequestBody SeatableTicketDeleteRequestDto requestDto) {
        return seatableTicketService.deleteByFilter(requestDto);
    }
}