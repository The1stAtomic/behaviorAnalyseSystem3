-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Host: 127.0.0.1
-- Generation Time: Jan 18, 2026 at 06:43 PM
-- Server version: 10.4.32-MariaDB
-- PHP Version: 8.2.12

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `face_att2`
--

-- --------------------------------------------------------

--
-- Table structure for table `attendance`
--

CREATE TABLE `attendance` (
  `attendance_id` int(11) NOT NULL,
  `schedule_id` int(11) NOT NULL,
  `student_id` int(11) NOT NULL,
  `attendance_date` date NOT NULL,
  `status` enum('Present','Absent','Late','Excused') DEFAULT 'Present',
  `remarks` text DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `attendance`
--

INSERT INTO `attendance` (`attendance_id`, `schedule_id`, `student_id`, `attendance_date`, `status`, `remarks`) VALUES
(1, 1, 2, '2026-01-19', 'Present', 'AI Accuracy: 23%'),
(2, 1, 6, '2026-01-19', 'Present', 'AI Accuracy: 37%'),
(3, 1, 7, '2026-01-19', 'Present', 'AI Accuracy: 23%'),
(4, 1, 1, '2026-01-19', 'Present', 'AI Accuracy: 24%');

-- --------------------------------------------------------

--
-- Table structure for table `classes`
--

CREATE TABLE `classes` (
  `class_id` int(11) NOT NULL,
  `subject_id` int(11) NOT NULL,
  `room_id` int(11) NOT NULL,
  `teacher_name` varchar(100) DEFAULT NULL,
  `day_of_week` enum('Monday','Tuesday','Wednesday','Thursday','Friday','Saturday') NOT NULL,
  `start_time` time NOT NULL,
  `end_time` time NOT NULL,
  `semester` varchar(20) DEFAULT 'Fall 2026'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `classes`
--

INSERT INTO `classes` (`class_id`, `subject_id`, `room_id`, `teacher_name`, `day_of_week`, `start_time`, `end_time`, `semester`) VALUES
(1, 1, 1, 'Mr. Panhasak', 'Monday', '08:00:00', '10:00:00', 'Semester 1'),
(2, 2, 2, 'Ms. Jenny', 'Tuesday', '13:00:00', '15:00:00', 'Semester 1'),
(3, 3, 1, 'Mr. Mony', 'Wednesday', '09:00:00', '11:00:00', 'Semester 1');

-- --------------------------------------------------------

--
-- Table structure for table `class_sessions`
--

CREATE TABLE `class_sessions` (
  `session_id` int(11) NOT NULL,
  `class_id` int(11) NOT NULL,
  `study_date` date NOT NULL,
  `topic_description` text DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `class_sessions`
--

INSERT INTO `class_sessions` (`session_id`, `class_id`, `study_date`, `topic_description`) VALUES
(101, 1, '2026-01-19', 'Week 01: Introduction & Course Overview'),
(102, 1, '2026-01-26', 'Week 02: Database Fundamentals'),
(103, 1, '2026-02-02', 'Week 03: Relational Algebra'),
(104, 1, '2026-02-09', 'Week 04: Advanced SQL Queries'),
(105, 1, '2026-02-16', 'Week 05: Data Normalization (1NF, 2NF, 3NF)'),
(106, 1, '2026-02-23', 'Week 06: Transaction Management'),
(107, 1, '2026-03-02', 'Week 07: Concurrency Control'),
(108, 1, '2026-03-09', 'Week 08: Midterm Review & Assessment'),
(109, 1, '2026-03-16', 'Week 09: NoSQL vs SQL Databases'),
(110, 1, '2026-03-23', 'Week 10: Database Security & Triggers'),
(111, 1, '2026-03-30', 'Week 11: Stored Procedures'),
(112, 1, '2026-04-06', 'Week 12: Indexing and Performance Tuning'),
(113, 1, '2026-04-13', 'Week 13: Database Connectivity (Python & MySQL)'),
(114, 1, '2026-04-20', 'Week 14: Final Project Preparation'),
(115, 1, '2026-04-27', 'Week 15: Final Course Presentation');

-- --------------------------------------------------------

--
-- Table structure for table `logs`
--

CREATE TABLE `logs` (
  `id` int(11) NOT NULL,
  `student_id` int(11) DEFAULT NULL,
  `name` varchar(255) NOT NULL,
  `accuracy` float NOT NULL,
  `timestamp` datetime DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `logs`
--

INSERT INTO `logs` (`id`, `student_id`, `name`, `accuracy`, `timestamp`) VALUES
(1, 2, 'sak5', 45, '2026-01-19 00:30:55'),
(2, 6, 'sak2', 35, '2026-01-19 00:30:58'),
(3, 1, 'sak4', 43, '2026-01-19 00:31:04'),
(4, 7, 'sak3', 20, '2026-01-19 00:32:10'),
(5, 6, 'sak2', 39, '2026-01-19 00:36:23'),
(6, 1, 'sak4', 35, '2026-01-19 00:36:25'),
(7, 2, 'sak5', 23, '2026-01-19 00:40:46'),
(8, 6, 'sak2', 37, '2026-01-19 00:42:02'),
(9, 7, 'sak3', 23, '2026-01-19 00:42:08'),
(10, 1, 'sak4', 24, '2026-01-19 00:42:11');

--
-- Triggers `logs`
--
DELIMITER $$
CREATE TRIGGER `attendance_trigger` AFTER INSERT ON `logs` FOR EACH ROW BEGIN
    -- This moves data from logs -> attendance automatically
    IF NEW.student_id IS NOT NULL THEN
        -- Verify if already present for today to prevent duplicates
        IF NOT EXISTS (
            SELECT 1 FROM attendance 
            WHERE student_id = NEW.student_id 
            AND attendance_date = DATE(NEW.timestamp)
        ) THEN
            -- Insert using the columns shown in your screenshot
            INSERT INTO attendance (schedule_id, student_id, attendance_date, status, remarks)
            VALUES (1, NEW.student_id, DATE(NEW.timestamp), 'Present', CONCAT('AI Accuracy: ', NEW.accuracy, '%'));
        END IF;
    END IF;
END
$$
DELIMITER ;

-- --------------------------------------------------------

--
-- Table structure for table `rooms`
--

CREATE TABLE `rooms` (
  `room_id` int(11) NOT NULL,
  `room_name` varchar(50) NOT NULL,
  `building_name` varchar(100) DEFAULT NULL,
  `floor_level` int(11) DEFAULT NULL,
  `capacity` int(11) NOT NULL,
  `room_type` enum('General','Laboratory','Lecture Hall','Office','Gym') DEFAULT 'General',
  `has_projector` tinyint(1) DEFAULT 0,
  `is_active` tinyint(1) DEFAULT 1,
  `last_cleaned` timestamp NULL DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `rooms`
--

INSERT INTO `rooms` (`room_id`, `room_name`, `building_name`, `floor_level`, `capacity`, `room_type`, `has_projector`, `is_active`, `last_cleaned`) VALUES
(1, 'Room 101', 'Main Academic Block', 1, 30, 'General', 1, 1, NULL),
(2, 'Biology Lab A', 'Science Center', 2, 24, 'Laboratory', 0, 1, NULL),
(3, 'Grand Auditorium', 'West Wing', 1, 250, 'Lecture Hall', 1, 1, NULL),
(4, 'Faculty Office 4', 'Administration Building', 3, 2, 'Office', 0, 1, NULL),
(5, 'Indoor Court', 'Sports Complex', 1, 100, 'Gym', 0, 1, NULL);

-- --------------------------------------------------------

--
-- Table structure for table `schedule`
--

CREATE TABLE `schedule` (
  `schedule_id` int(11) NOT NULL,
  `subject_id` int(11) NOT NULL,
  `room_id` int(11) NOT NULL,
  `teacher_id` int(11) DEFAULT NULL,
  `day_of_week` enum('Mon','Tue','Wed','Thu','Fri','Sat','Sun') NOT NULL,
  `start_time` time NOT NULL,
  `end_time` time NOT NULL,
  `academic_year` varchar(10) DEFAULT NULL,
  `semester` int(11) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `schedule`
--

INSERT INTO `schedule` (`schedule_id`, `subject_id`, `room_id`, `teacher_id`, `day_of_week`, `start_time`, `end_time`, `academic_year`, `semester`) VALUES
(1, 1, 1, NULL, 'Mon', '08:00:00', '09:30:00', '2025-2026', 1),
(2, 2, 2, NULL, 'Mon', '10:00:00', '12:00:00', '2025-2026', 1),
(3, 3, 3, NULL, 'Tue', '13:00:00', '14:30:00', '2025-2026', 1),
(4, 4, 1, NULL, 'Wed', '09:00:00', '11:00:00', '2025-2026', 1),
(5, 5, 4, NULL, 'Thu', '15:00:00', '16:00:00', '2025-2026', 1);

-- --------------------------------------------------------

--
-- Table structure for table `students`
--

CREATE TABLE `students` (
  `student_id` int(11) NOT NULL,
  `first_name` varchar(50) NOT NULL,
  `last_name` varchar(50) NOT NULL,
  `enrollment_date` date DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `students`
--

INSERT INTO `students` (`student_id`, `first_name`, `last_name`, `enrollment_date`) VALUES
(1, 'sak4', 'sak', '2024-01-10'),
(2, 'sak5', 'sak', '2024-01-12'),
(3, 'mony', 'mony', '2024-01-15'),
(4, 'jenny', 'jenny', '2024-01-18'),
(5, 'votta', 'votta', '2024-01-20'),
(6, 'Sak2', 'Student', '2025-01-20'),
(7, 'Sak3', 'Student', '2025-01-21');

-- --------------------------------------------------------

--
-- Table structure for table `student_schedules`
--

CREATE TABLE `student_schedules` (
  `enrollment_id` int(11) NOT NULL,
  `student_id` int(11) NOT NULL,
  `schedule_id` int(11) NOT NULL,
  `class_id` int(11) NOT NULL,
  `academic_year` varchar(20) DEFAULT '2025-2026',
  `status` enum('Active','Dropped','Completed') DEFAULT 'Active'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `student_schedules`
--

INSERT INTO `student_schedules` (`enrollment_id`, `student_id`, `schedule_id`, `class_id`, `academic_year`, `status`) VALUES
(1, 1, 1, 1, '2025-2026', 'Active'),
(2, 2, 1, 1, '2025-2026', 'Active'),
(3, 3, 2, 2, '2025-2026', 'Active');

-- --------------------------------------------------------

--
-- Table structure for table `subjects`
--

CREATE TABLE `subjects` (
  `subject_id` int(11) NOT NULL,
  `subject_code` varchar(20) NOT NULL,
  `subject_name` varchar(100) NOT NULL,
  `description` text DEFAULT NULL,
  `credits` int(11) DEFAULT 3,
  `department` enum('Math','Science','History','Arts','IT','PE') NOT NULL,
  `is_elective` tinyint(1) DEFAULT 0,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `subjects`
--

INSERT INTO `subjects` (`subject_id`, `subject_code`, `subject_name`, `description`, `credits`, `department`, `is_elective`, `created_at`) VALUES
(1, 'MATH-101', 'Introduction to Algebra', NULL, 3, 'Math', 0, '2026-01-18 16:38:51'),
(2, 'PHYS-201', 'General Physics I', NULL, 4, 'Science', 0, '2026-01-18 16:38:51'),
(3, 'HIST-110', 'World History', NULL, 3, 'History', 1, '2026-01-18 16:38:51'),
(4, 'CS-105', 'Introduction to Python', NULL, 4, 'IT', 0, '2026-01-18 16:38:51'),
(5, 'ART-150', 'Digital Photography', NULL, 2, 'Arts', 1, '2026-01-18 16:38:51');

--
-- Indexes for dumped tables
--

--
-- Indexes for table `attendance`
--
ALTER TABLE `attendance`
  ADD PRIMARY KEY (`attendance_id`),
  ADD UNIQUE KEY `unique_daily_attendance` (`schedule_id`,`student_id`,`attendance_date`),
  ADD KEY `fk_attendance_student_link` (`student_id`);

--
-- Indexes for table `classes`
--
ALTER TABLE `classes`
  ADD PRIMARY KEY (`class_id`),
  ADD KEY `subject_id` (`subject_id`),
  ADD KEY `room_id` (`room_id`);

--
-- Indexes for table `class_sessions`
--
ALTER TABLE `class_sessions`
  ADD PRIMARY KEY (`session_id`),
  ADD KEY `fk_session_class` (`class_id`);

--
-- Indexes for table `logs`
--
ALTER TABLE `logs`
  ADD PRIMARY KEY (`id`),
  ADD KEY `fk_logs_student` (`student_id`);

--
-- Indexes for table `rooms`
--
ALTER TABLE `rooms`
  ADD PRIMARY KEY (`room_id`);

--
-- Indexes for table `schedule`
--
ALTER TABLE `schedule`
  ADD PRIMARY KEY (`schedule_id`),
  ADD KEY `fk_room` (`room_id`),
  ADD KEY `fk_subject` (`subject_id`);

--
-- Indexes for table `students`
--
ALTER TABLE `students`
  ADD PRIMARY KEY (`student_id`);

--
-- Indexes for table `student_schedules`
--
ALTER TABLE `student_schedules`
  ADD PRIMARY KEY (`enrollment_id`),
  ADD KEY `fk_student` (`student_id`),
  ADD KEY `fk_class` (`class_id`);

--
-- Indexes for table `subjects`
--
ALTER TABLE `subjects`
  ADD PRIMARY KEY (`subject_id`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `attendance`
--
ALTER TABLE `attendance`
  MODIFY `attendance_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=5;

--
-- AUTO_INCREMENT for table `classes`
--
ALTER TABLE `classes`
  MODIFY `class_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=4;

--
-- AUTO_INCREMENT for table `class_sessions`
--
ALTER TABLE `class_sessions`
  MODIFY `session_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=116;

--
-- AUTO_INCREMENT for table `logs`
--
ALTER TABLE `logs`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=11;

--
-- AUTO_INCREMENT for table `rooms`
--
ALTER TABLE `rooms`
  MODIFY `room_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=6;

--
-- AUTO_INCREMENT for table `schedule`
--
ALTER TABLE `schedule`
  MODIFY `schedule_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=6;

--
-- AUTO_INCREMENT for table `students`
--
ALTER TABLE `students`
  MODIFY `student_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=8;

--
-- AUTO_INCREMENT for table `student_schedules`
--
ALTER TABLE `student_schedules`
  MODIFY `enrollment_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=4;

--
-- AUTO_INCREMENT for table `subjects`
--
ALTER TABLE `subjects`
  MODIFY `subject_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=6;

--
-- Constraints for dumped tables
--

--
-- Constraints for table `attendance`
--
ALTER TABLE `attendance`
  ADD CONSTRAINT `fk_attendance_schedule` FOREIGN KEY (`schedule_id`) REFERENCES `schedule` (`schedule_id`),
  ADD CONSTRAINT `fk_attendance_student` FOREIGN KEY (`student_id`) REFERENCES `students` (`student_id`),
  ADD CONSTRAINT `fk_attendance_student_link` FOREIGN KEY (`student_id`) REFERENCES `students` (`student_id`) ON DELETE CASCADE;

--
-- Constraints for table `classes`
--
ALTER TABLE `classes`
  ADD CONSTRAINT `classes_ibfk_1` FOREIGN KEY (`subject_id`) REFERENCES `subjects` (`subject_id`),
  ADD CONSTRAINT `classes_ibfk_2` FOREIGN KEY (`room_id`) REFERENCES `rooms` (`room_id`);

--
-- Constraints for table `class_sessions`
--
ALTER TABLE `class_sessions`
  ADD CONSTRAINT `fk_session_class` FOREIGN KEY (`class_id`) REFERENCES `classes` (`class_id`) ON DELETE CASCADE;

--
-- Constraints for table `logs`
--
ALTER TABLE `logs`
  ADD CONSTRAINT `fk_logs_student` FOREIGN KEY (`student_id`) REFERENCES `students` (`student_id`) ON DELETE CASCADE;

--
-- Constraints for table `schedule`
--
ALTER TABLE `schedule`
  ADD CONSTRAINT `fk_room` FOREIGN KEY (`room_id`) REFERENCES `rooms` (`room_id`) ON DELETE CASCADE,
  ADD CONSTRAINT `fk_subject` FOREIGN KEY (`subject_id`) REFERENCES `subjects` (`subject_id`) ON DELETE CASCADE;

--
-- Constraints for table `student_schedules`
--
ALTER TABLE `student_schedules`
  ADD CONSTRAINT `fk_class` FOREIGN KEY (`class_id`) REFERENCES `classes` (`class_id`) ON DELETE CASCADE,
  ADD CONSTRAINT `fk_student` FOREIGN KEY (`student_id`) REFERENCES `students` (`student_id`) ON DELETE CASCADE;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
