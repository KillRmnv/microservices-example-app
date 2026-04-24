package com.microservices_example_app.users.service;

import com.microservices_example_app.users.dto.*;
import com.microservices_example_app.users.exceptions.UserNotFoundException;
import com.microservices_example_app.users.model.Role;
import com.microservices_example_app.users.model.User;
import com.microservices_example_app.users.repository.RoleRepository;
import com.microservices_example_app.users.repository.UserRepository;
import com.microservices_example_app.users.utils.JwtUtil;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;


@Service
public final class UserService {

    private final UserRepository userDao;
    private final RoleRepository roleRepository;
    private final PasswordService passwordService;

    public UserService(UserRepository userDao, RoleRepository roleRepository, PasswordService passwordService) {
        this.userDao = userDao;
        this.roleRepository = roleRepository;
        this.passwordService = passwordService;
    }

    @Transactional
    public UserRegistrationDto register(String email, String password, String role, String username) {
        Role customerRole = roleRepository.findByName(role).orElseThrow(() -> new IllegalStateException("Role not found"));

        String hash = passwordService.hash(password);

        User user = User.builder().username(username).email(email).passwordHash(hash).userRole(customerRole).build();

        User saved = userDao.save(user);

        return new UserRegistrationDto(saved.getId(), saved.getUsername(), saved.getEmail());
    }

    @Transactional(readOnly = true)
    public UserLoginResponseDto login(String email, String password) {
        User user = userDao.findByEmail(email).orElseThrow(() -> new UserNotFoundException("Invalid email or password"));

        if (!passwordService.verify(password, user.getPasswordHash())) {
            throw new IllegalArgumentException("Invalid email or password");
        }
        return new UserLoginResponseDto(JwtUtil.generateToken(user.getUsername(), user.getEmail(), user.getUserRole().getName()), user.getId());

    }

    @Transactional(readOnly = true)
    public UserResponseDto getByEmail(String email) {
        User user = userDao.findByEmail(email).orElseThrow(() -> new UserNotFoundException("User not found: " + email));

        return toResponseDto(user);
    }

    //TODO: implement
    public PasswordRestoringResponse restorePassword(String email) {
        return null;
    }

    private UserResponseDto toResponseDto(User user) {
        return new UserResponseDto(user.getId(), user.getUsername(), user.getEmail(), user.getUserRole().getName());
    }

    @Transactional
    public List<UserResponseDto> getAll() {
        return userDao.findAll().stream().map(this::toResponseDto).toList();
    }
    @Transactional
    public List<UserResponseDto> getUsersByPage(int page, int size) {
        Pageable pageable = PageRequest.of(page - 1, size);
        return userDao.findAll(pageable).stream().map(this::toResponseDto).toList();
    }
    @Transactional
    public UserResponseDto getById(int id) {
        return toResponseDto(userDao.findById(id).orElseThrow(() -> new UserNotFoundException("no such user")));
    }
    @Transactional
    public void updateUser(User updatedUser) {
        userDao.findById(updatedUser.getId()).orElseThrow(() -> new UserNotFoundException("no user with such id"));
        userDao.save(updatedUser);
    }
    @Transactional
    public void deleteUser(UserDeleteRequestDto userToDelete) {
        userDao.findById(userToDelete.getId()).orElseThrow(() -> new UserNotFoundException("no user with such id"));
        userDao.deleteById(userToDelete.getId());
    }

    @Transactional
    public long deleteByFilter(UserDeleteRequestDto userDto) {
        Specification<User> spec = Specification
                .where(UserSpecification.hasEmail(userDto.getEmail()))
                .and(UserSpecification.hasUsername(userDto.getUsername()))
                .and(userDto.getRole() == null ? null :
                        UserSpecification.hasRole(
                                roleRepository.findByName(userDto.getRole())
                                .orElseThrow(() -> new IllegalArgumentException("Role not found: " + userDto.getRole()))
                        ));

        List<User> users = userDao.findAll(spec);
        long count = users.size();
        userDao.deleteAll(users);
        return count;
    }

    @Transactional(readOnly = true)
    public List<UserResponseDto> searchByFilter(UserSerchRequestDto filter) {
        Specification<User> spec = Specification.where((Specification<User>) null);

        if (filter.getEmail() != null && !filter.getEmail().isBlank()) {
            spec = spec.and(UserSpecification.hasEmail(filter.getEmail()));
        }

        if (filter.getUsername() != null && !filter.getUsername().isBlank()) {
            spec = spec.and(UserSpecification.hasUsername(filter.getUsername()));
        }

        if (filter.getRole() != null && !filter.getRole().isBlank()) {
            Role role = roleRepository.findByName(filter.getRole())
                    .orElseThrow(() -> new IllegalArgumentException("Role not found: " + filter.getRole()));
            spec = spec.and(UserSpecification.hasRole(role));
        }

        return userDao.findAll(spec)
                .stream()
                .map(this::toResponseDto)
                .toList();
    }

    @Transactional(readOnly = true)
    public List<UserResponseDto> searchByFilter(UserSerchRequestDto filter, int page, int size) {
        if (page < 1) {
            throw new IllegalArgumentException("Page must be >= 1");
        }
        if (size < 1) {
            throw new IllegalArgumentException("Size must be >= 1");
        }

        Specification<User> spec = Specification.where((Specification<User>) null);

        if (filter.getEmail() != null && !filter.getEmail().isBlank()) {
            spec = spec.and(UserSpecification.hasEmail(filter.getEmail()));
        }

        if (filter.getUsername() != null && !filter.getUsername().isBlank()) {
            spec = spec.and(UserSpecification.hasUsername(filter.getUsername()));
        }

        if (filter.getRole() != null && !filter.getRole().isBlank()) {
            Role role = roleRepository.findByName(filter.getRole())
                    .orElseThrow(() -> new IllegalArgumentException("Role not found: " + filter.getRole()));
            spec = spec.and(UserSpecification.hasRole(role));
        }

        Pageable pageable = PageRequest.of(page - 1, size);

        return userDao.findAll(spec, pageable)
                .stream()
                .map(this::toResponseDto)
                .toList();
    }

    @Transactional
    public UserResponseDto updateUserById(UserUpdateRequestDto request) {
        if (request.getId() < 0) {
            throw new IllegalArgumentException("User id must be positive");
        }

        User user = userDao.findById(request.getId())
                .orElseThrow(() -> new UserNotFoundException("No user with id=" + request.getId()));
        var builder = User.builder();
        if (request.getEmail() != null && !request.getEmail().isBlank()) {
            userDao.findByEmail(request.getEmail())
                    .filter(existing -> !(existing.getId() == user.getId()))
                    .ifPresent(existing -> {
                        throw new IllegalArgumentException("Email already in use: " + request.getEmail());
                    });
            builder.email(request.getEmail());
        } else {
            builder.email(user.getEmail());
        }

        if (request.getUsername() != null && !request.getUsername().isBlank()) {
            builder.username(request.getUsername());
        } else {
            builder.username(user.getUsername());
        }

        if (request.getRole() != null && !request.getRole().isBlank()) {
            Role role = roleRepository.findByName(request.getRole())
                    .orElseThrow(() -> new IllegalArgumentException("Role not found: " + request.getRole()));
            builder.userRole(role);
        } else {
            builder.userRole(user.getUserRole());
        }

        if (request.getPassword() != null && !request.getPassword().isBlank()) {
            builder.passwordHash(passwordService.hash(request.getPassword()));
        } else {
            builder.passwordHash(user.getPasswordHash());
        }

        User saved = userDao.save(builder.build());
        return toResponseDto(saved);
    }
}
