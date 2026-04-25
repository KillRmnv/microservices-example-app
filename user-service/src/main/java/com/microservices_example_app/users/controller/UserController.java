package com.microservices_example_app.users.controller;

import com.microservices_example_app.users.dto.*;
import com.microservices_example_app.users.service.UserService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/users")
public class UserController {

    private final UserService userService;

    public UserController(UserService userService) {
        this.userService = userService;
    }

    @GetMapping
    public ResponseEntity<List<UserResponseDto>> getAll() {
        return ResponseEntity.ok(userService.getAll());
    }

    @GetMapping("/{id}")
    public ResponseEntity<UserResponseDto> getById(@PathVariable int id) {
        return ResponseEntity.ok(userService.getById(id));
    }

    @GetMapping("/by-email")
    public ResponseEntity<UserResponseDto> getByEmail(@RequestParam String email) {
        return ResponseEntity.ok(userService.getByEmail(email));
    }

    @GetMapping("/page")
    public ResponseEntity<List<UserResponseDto>> getUsersByPage(
            @RequestParam int page,
            @RequestParam int size
    ) {
        return ResponseEntity.ok(userService.getUsersByPage(page, size));
    }

    @GetMapping("/search")
    public ResponseEntity<List<UserResponseDto>> searchByFilter(@ModelAttribute UserSerchRequestDto filter) {
        return ResponseEntity.ok(userService.searchByFilter(filter));
    }

    @GetMapping("/search/page")
    public ResponseEntity<List<UserResponseDto>> searchByFilterWithPage(
            @ModelAttribute UserSerchRequestDto filter,
            @RequestParam int page,
            @RequestParam int size
    ) {
        return ResponseEntity.ok(userService.searchByFilter(filter, page, size));
    }

    @PutMapping
    public ResponseEntity<UserResponseDto> updateUser(@RequestBody UserUpdateRequestDto request) {
        return ResponseEntity.ok(userService.updateUserById(request));
    }

    @DeleteMapping
    public ResponseEntity<Void> deleteUser(@RequestBody UserDeleteRequestDto request) {
        userService.deleteUser(request);
        return ResponseEntity.noContent().build();
    }

    @DeleteMapping("/search")
    public ResponseEntity<Long> deleteByFilter(@RequestBody UserDeleteRequestDto request) {
        return ResponseEntity.ok(userService.deleteByFilter(request));
    }
}