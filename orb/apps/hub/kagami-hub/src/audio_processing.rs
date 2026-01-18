//! Optimized Audio Processing — Spark (e1) Colony
//!
//! High-performance audio processing with:
//! - SIMD acceleration for sample conversion and processing
//! - Zero-copy buffer management
//! - Reduced memory allocation through buffer pools
//! - Optimized resampling and normalization
//!
//! ## Architecture
//!
//! ```text
//! Audio Input -> Ring Buffer -> SIMD Convert -> Pre-Process -> STT
//!                    |             |               |
//!                    |             v               v
//!                    |         Zero-Copy       Buffer Pool
//!                    |             |               |
//!                    +-------------+---------------+
//!                                  |
//!                            Memory Reuse
//! ```
//!
//! Colony: Spark (e1) — Energy, initiative
//!
//! h(x) >= 0. Always.

use std::sync::atomic::{AtomicUsize, Ordering};

#[cfg(target_arch = "x86_64")]
use std::arch::x86_64::*;

#[cfg(target_arch = "aarch64")]
use std::arch::aarch64::*;

// ============================================================================
// Configuration
// ============================================================================

/// Sample rate for Whisper (16kHz)
pub const WHISPER_SAMPLE_RATE: u32 = 16000;

/// Default audio buffer size (samples)
pub const DEFAULT_BUFFER_SIZE: usize = 16000; // 1 second at 16kHz

/// Maximum audio buffer size (samples)
pub const MAX_BUFFER_SIZE: usize = 480000; // 30 seconds at 16kHz

/// Buffer pool size
pub const BUFFER_POOL_SIZE: usize = 8;

/// SIMD vector size for processing
pub const SIMD_VECTOR_SIZE: usize = 8; // AVX2 processes 8 floats at once

// ============================================================================
// Zero-Copy Ring Buffer
// ============================================================================

/// Zero-copy ring buffer for audio samples
/// Uses power-of-two sizing for fast modulo with bitwise AND
pub struct RingBuffer<T: Copy + Default> {
    /// Buffer storage
    data: Box<[T]>,
    /// Write position
    write_pos: AtomicUsize,
    /// Read position
    read_pos: AtomicUsize,
    /// Capacity (power of 2)
    capacity: usize,
    /// Mask for fast modulo (capacity - 1)
    mask: usize,
}

impl<T: Copy + Default> RingBuffer<T> {
    /// Create a new ring buffer with given capacity (will be rounded up to power of 2)
    pub fn new(min_capacity: usize) -> Self {
        // Round up to next power of 2
        let capacity = min_capacity.next_power_of_two();
        let mask = capacity - 1;

        // Allocate uninitialized buffer
        let data = vec![T::default(); capacity].into_boxed_slice();

        Self {
            data,
            write_pos: AtomicUsize::new(0),
            read_pos: AtomicUsize::new(0),
            capacity,
            mask,
        }
    }

    /// Write samples to buffer (returns number of samples written)
    #[inline]
    pub fn write(&self, samples: &[T]) -> usize {
        let write_pos = self.write_pos.load(Ordering::Acquire);
        let read_pos = self.read_pos.load(Ordering::Acquire);

        // Calculate available space
        let available = self.capacity - (write_pos - read_pos);
        let to_write = samples.len().min(available);

        if to_write == 0 {
            return 0;
        }

        // Get mutable reference to data (safe because we're the only writer)
        let data = unsafe {
            std::slice::from_raw_parts_mut(
                self.data.as_ptr() as *mut T,
                self.capacity
            )
        };

        // Write in two parts if wrapping
        let start = write_pos & self.mask;
        let end = (write_pos + to_write) & self.mask;

        if end > start || to_write <= self.capacity - start {
            // No wrap
            data[start..start + to_write].copy_from_slice(&samples[..to_write]);
        } else {
            // Wrap around
            let first_chunk = self.capacity - start;
            data[start..].copy_from_slice(&samples[..first_chunk]);
            data[..end].copy_from_slice(&samples[first_chunk..to_write]);
        }

        self.write_pos.store(write_pos + to_write, Ordering::Release);
        to_write
    }

    /// Read samples from buffer into provided slice (returns number of samples read)
    #[inline]
    pub fn read(&self, output: &mut [T]) -> usize {
        let write_pos = self.write_pos.load(Ordering::Acquire);
        let read_pos = self.read_pos.load(Ordering::Acquire);

        // Calculate available data
        let available = write_pos - read_pos;
        let to_read = output.len().min(available);

        if to_read == 0 {
            return 0;
        }

        let start = read_pos & self.mask;
        let end = (read_pos + to_read) & self.mask;

        if end > start || to_read <= self.capacity - start {
            // No wrap
            output[..to_read].copy_from_slice(&self.data[start..start + to_read]);
        } else {
            // Wrap around
            let first_chunk = self.capacity - start;
            output[..first_chunk].copy_from_slice(&self.data[start..]);
            output[first_chunk..to_read].copy_from_slice(&self.data[..end]);
        }

        self.read_pos.store(read_pos + to_read, Ordering::Release);
        to_read
    }

    /// Peek at samples without consuming (returns slice views)
    #[inline]
    pub fn peek(&self, count: usize) -> (&[T], &[T]) {
        let write_pos = self.write_pos.load(Ordering::Acquire);
        let read_pos = self.read_pos.load(Ordering::Acquire);

        let available = write_pos - read_pos;
        let to_peek = count.min(available);

        let start = read_pos & self.mask;
        let end = (read_pos + to_peek) & self.mask;

        if end > start || to_peek <= self.capacity - start {
            // No wrap - single contiguous slice
            (&self.data[start..start + to_peek], &[])
        } else {
            // Wrap around - two slices
            let first_chunk = self.capacity - start;
            (&self.data[start..], &self.data[..end])
        }
    }

    /// Get number of samples available for reading
    #[inline]
    pub fn available(&self) -> usize {
        let write_pos = self.write_pos.load(Ordering::Acquire);
        let read_pos = self.read_pos.load(Ordering::Acquire);
        write_pos - read_pos
    }

    /// Get free space for writing
    #[inline]
    pub fn free_space(&self) -> usize {
        self.capacity - self.available()
    }

    /// Clear the buffer
    pub fn clear(&self) {
        self.read_pos.store(self.write_pos.load(Ordering::Acquire), Ordering::Release);
    }
}

// ============================================================================
// Buffer Pool
// ============================================================================

/// Pool of reusable buffers to reduce allocation
pub struct BufferPool<T: Copy + Default> {
    /// Available buffers
    buffers: Vec<Vec<T>>,
    /// Buffer size
    buffer_size: usize,
    /// Number of buffers currently in use
    in_use: AtomicUsize,
}

impl<T: Copy + Default> BufferPool<T> {
    /// Create a new buffer pool
    pub fn new(pool_size: usize, buffer_size: usize) -> Self {
        let mut buffers = Vec::with_capacity(pool_size);
        for _ in 0..pool_size {
            buffers.push(vec![T::default(); buffer_size]);
        }

        Self {
            buffers,
            buffer_size,
            in_use: AtomicUsize::new(0),
        }
    }

    /// Acquire a buffer from the pool
    pub fn acquire(&mut self) -> Option<Vec<T>> {
        if let Some(buffer) = self.buffers.pop() {
            self.in_use.fetch_add(1, Ordering::Relaxed);
            Some(buffer)
        } else {
            // Pool exhausted, allocate new buffer
            self.in_use.fetch_add(1, Ordering::Relaxed);
            Some(vec![T::default(); self.buffer_size])
        }
    }

    /// Return a buffer to the pool
    pub fn release(&mut self, mut buffer: Vec<T>) {
        self.in_use.fetch_sub(1, Ordering::Relaxed);

        // Only keep if pool isn't full
        if self.buffers.len() < BUFFER_POOL_SIZE {
            buffer.clear();
            buffer.resize(self.buffer_size, T::default());
            self.buffers.push(buffer);
        }
        // Otherwise let it drop
    }

    /// Get number of buffers in use
    pub fn in_use(&self) -> usize {
        self.in_use.load(Ordering::Relaxed)
    }
}

// ============================================================================
// SIMD Audio Conversion
// ============================================================================

/// Convert i16 samples to f32 with SIMD acceleration
#[inline]
pub fn convert_i16_to_f32_simd(input: &[i16], output: &mut [f32]) {
    assert!(output.len() >= input.len());

    #[cfg(all(target_arch = "x86_64", target_feature = "avx2"))]
    {
        convert_i16_to_f32_avx2(input, output);
        return;
    }

    #[cfg(all(target_arch = "aarch64", target_feature = "neon"))]
    {
        convert_i16_to_f32_neon(input, output);
        return;
    }

    // Fallback scalar implementation
    convert_i16_to_f32_scalar(input, output);
}

/// AVX2 implementation for x86_64
#[cfg(all(target_arch = "x86_64", target_feature = "avx2"))]
#[inline]
fn convert_i16_to_f32_avx2(input: &[i16], output: &mut [f32]) {
    unsafe {
        let scale = _mm256_set1_ps(1.0 / 32768.0);
        let len = input.len();
        let chunks = len / 8;

        for i in 0..chunks {
            let offset = i * 8;

            // Load 8 i16 values (128 bits)
            let i16_ptr = input.as_ptr().add(offset) as *const __m128i;
            let i16_vec = _mm_loadu_si128(i16_ptr);

            // Convert i16 to i32 (sign extend)
            let i32_lo = _mm256_cvtepi16_epi32(i16_vec);

            // Convert i32 to f32
            let f32_vec = _mm256_cvtepi32_ps(i32_lo);

            // Scale to [-1, 1]
            let scaled = _mm256_mul_ps(f32_vec, scale);

            // Store result
            let f32_ptr = output.as_mut_ptr().add(offset);
            _mm256_storeu_ps(f32_ptr, scaled);
        }

        // Handle remaining samples
        let remaining = chunks * 8;
        for i in remaining..len {
            output[i] = input[i] as f32 / 32768.0;
        }
    }
}

/// NEON implementation for ARM64
#[cfg(all(target_arch = "aarch64", target_feature = "neon"))]
#[inline]
fn convert_i16_to_f32_neon(input: &[i16], output: &mut [f32]) {
    unsafe {
        let scale = vdupq_n_f32(1.0 / 32768.0);
        let len = input.len();
        let chunks = len / 4;

        for i in 0..chunks {
            let offset = i * 4;

            // Load 4 i16 values
            let i16_ptr = input.as_ptr().add(offset);
            let i16_vec = vld1_s16(i16_ptr);

            // Convert i16 to i32 (sign extend)
            let i32_vec = vmovl_s16(i16_vec);

            // Convert i32 to f32
            let f32_vec = vcvtq_f32_s32(i32_vec);

            // Scale to [-1, 1]
            let scaled = vmulq_f32(f32_vec, scale);

            // Store result
            let f32_ptr = output.as_mut_ptr().add(offset);
            vst1q_f32(f32_ptr, scaled);
        }

        // Handle remaining samples
        let remaining = chunks * 4;
        for i in remaining..len {
            output[i] = input[i] as f32 / 32768.0;
        }
    }
}

/// Scalar fallback implementation
#[inline]
fn convert_i16_to_f32_scalar(input: &[i16], output: &mut [f32]) {
    const SCALE: f32 = 1.0 / 32768.0;

    // Process 4 at a time for better pipelining
    let chunks = input.len() / 4;

    for i in 0..chunks {
        let offset = i * 4;
        output[offset] = input[offset] as f32 * SCALE;
        output[offset + 1] = input[offset + 1] as f32 * SCALE;
        output[offset + 2] = input[offset + 2] as f32 * SCALE;
        output[offset + 3] = input[offset + 3] as f32 * SCALE;
    }

    // Handle remaining
    for i in (chunks * 4)..input.len() {
        output[i] = input[i] as f32 * SCALE;
    }
}

// ============================================================================
// SIMD Audio Analysis
// ============================================================================

/// Calculate RMS energy with SIMD
#[inline]
pub fn calculate_rms_simd(samples: &[f32]) -> f32 {
    if samples.is_empty() {
        return 0.0;
    }

    #[cfg(all(target_arch = "x86_64", target_feature = "avx2"))]
    {
        return calculate_rms_avx2(samples);
    }

    #[cfg(all(target_arch = "aarch64", target_feature = "neon"))]
    {
        return calculate_rms_neon(samples);
    }

    // Fallback
    calculate_rms_scalar(samples)
}

/// AVX2 RMS calculation
#[cfg(all(target_arch = "x86_64", target_feature = "avx2"))]
#[inline]
fn calculate_rms_avx2(samples: &[f32]) -> f32 {
    unsafe {
        let mut sum_vec = _mm256_setzero_ps();
        let chunks = samples.len() / 8;

        for i in 0..chunks {
            let offset = i * 8;
            let ptr = samples.as_ptr().add(offset);
            let vec = _mm256_loadu_ps(ptr);
            let squared = _mm256_mul_ps(vec, vec);
            sum_vec = _mm256_add_ps(sum_vec, squared);
        }

        // Horizontal sum
        let mut sum_array = [0.0f32; 8];
        _mm256_storeu_ps(sum_array.as_mut_ptr(), sum_vec);
        let mut sum: f32 = sum_array.iter().sum();

        // Handle remaining
        for i in (chunks * 8)..samples.len() {
            sum += samples[i] * samples[i];
        }

        (sum / samples.len() as f32).sqrt()
    }
}

/// NEON RMS calculation
#[cfg(all(target_arch = "aarch64", target_feature = "neon"))]
#[inline]
fn calculate_rms_neon(samples: &[f32]) -> f32 {
    unsafe {
        let mut sum_vec = vdupq_n_f32(0.0);
        let chunks = samples.len() / 4;

        for i in 0..chunks {
            let offset = i * 4;
            let ptr = samples.as_ptr().add(offset);
            let vec = vld1q_f32(ptr);
            let squared = vmulq_f32(vec, vec);
            sum_vec = vaddq_f32(sum_vec, squared);
        }

        // Horizontal sum
        let sum = vaddvq_f32(sum_vec);

        // Handle remaining
        let mut total_sum = sum;
        for i in (chunks * 4)..samples.len() {
            total_sum += samples[i] * samples[i];
        }

        (total_sum / samples.len() as f32).sqrt()
    }
}

/// Scalar RMS calculation
#[inline]
fn calculate_rms_scalar(samples: &[f32]) -> f32 {
    let mut sum = 0.0f32;
    let chunks = samples.len() / 4;

    for i in 0..chunks {
        let offset = i * 4;
        sum += samples[offset] * samples[offset];
        sum += samples[offset + 1] * samples[offset + 1];
        sum += samples[offset + 2] * samples[offset + 2];
        sum += samples[offset + 3] * samples[offset + 3];
    }

    for i in (chunks * 4)..samples.len() {
        sum += samples[i] * samples[i];
    }

    (sum / samples.len() as f32).sqrt()
}

/// Find peak amplitude with SIMD
#[inline]
pub fn find_peak_simd(samples: &[f32]) -> f32 {
    if samples.is_empty() {
        return 0.0;
    }

    #[cfg(all(target_arch = "x86_64", target_feature = "avx2"))]
    {
        return find_peak_avx2(samples);
    }

    // Fallback
    find_peak_scalar(samples)
}

/// AVX2 peak finding
#[cfg(all(target_arch = "x86_64", target_feature = "avx2"))]
#[inline]
fn find_peak_avx2(samples: &[f32]) -> f32 {
    unsafe {
        let sign_mask = _mm256_set1_ps(-0.0);
        let mut max_vec = _mm256_setzero_ps();
        let chunks = samples.len() / 8;

        for i in 0..chunks {
            let offset = i * 8;
            let ptr = samples.as_ptr().add(offset);
            let vec = _mm256_loadu_ps(ptr);
            // Absolute value
            let abs_vec = _mm256_andnot_ps(sign_mask, vec);
            max_vec = _mm256_max_ps(max_vec, abs_vec);
        }

        // Find max in vector
        let mut max_array = [0.0f32; 8];
        _mm256_storeu_ps(max_array.as_mut_ptr(), max_vec);
        let mut max_val = max_array.iter().cloned().fold(0.0f32, f32::max);

        // Handle remaining
        for i in (chunks * 8)..samples.len() {
            max_val = max_val.max(samples[i].abs());
        }

        max_val
    }
}

/// Scalar peak finding
#[inline]
fn find_peak_scalar(samples: &[f32]) -> f32 {
    samples.iter().map(|s| s.abs()).fold(0.0f32, f32::max)
}

// ============================================================================
// Optimized Audio Pre-processor
// ============================================================================

/// Optimized audio pre-processor with buffer pooling
pub struct AudioPreprocessor {
    /// Input ring buffer (i16 samples)
    input_buffer: RingBuffer<i16>,
    /// Output buffer pool (f32 samples)
    output_pool: BufferPool<f32>,
    /// Temporary buffer for conversion
    temp_buffer: Vec<f32>,
    /// Sample rate
    sample_rate: u32,
    /// Silence threshold
    silence_threshold: f32,
    /// Minimum speech length (samples)
    min_speech_samples: usize,
}

impl AudioPreprocessor {
    /// Create a new audio preprocessor
    pub fn new(buffer_size: usize, sample_rate: u32) -> Self {
        Self {
            input_buffer: RingBuffer::new(buffer_size),
            output_pool: BufferPool::new(BUFFER_POOL_SIZE, buffer_size),
            temp_buffer: vec![0.0f32; buffer_size],
            sample_rate,
            silence_threshold: 0.01,
            min_speech_samples: sample_rate as usize / 4, // 250ms
        }
    }

    /// Write raw audio samples to buffer
    #[inline]
    pub fn write(&self, samples: &[i16]) -> usize {
        self.input_buffer.write(samples)
    }

    /// Check if we have enough audio for processing
    #[inline]
    pub fn has_speech(&self) -> bool {
        let available = self.input_buffer.available();
        if available < self.min_speech_samples {
            return false;
        }

        // Quick energy check using peek (zero-copy)
        let (part1, part2) = self.input_buffer.peek(self.min_speech_samples);

        // Calculate energy from i16 samples directly
        let mut sum = 0i64;
        for &s in part1.iter().chain(part2.iter()) {
            sum += (s as i64) * (s as i64);
        }

        let rms = ((sum as f64) / (part1.len() + part2.len()) as f64).sqrt() / 32768.0;
        rms > self.silence_threshold as f64
    }

    /// Process and extract audio for STT (zero-copy optimized)
    pub fn extract(&mut self) -> Option<Vec<f32>> {
        let available = self.input_buffer.available();
        if available < self.min_speech_samples {
            return None;
        }

        // Acquire buffer from pool
        let mut output = self.output_pool.acquire()?;
        output.resize(available, 0.0);

        // Read i16 samples
        let mut i16_buffer = vec![0i16; available];
        let read_count = self.input_buffer.read(&mut i16_buffer);

        if read_count == 0 {
            self.output_pool.release(output);
            return None;
        }

        // Convert with SIMD
        convert_i16_to_f32_simd(&i16_buffer[..read_count], &mut output);
        output.truncate(read_count);

        Some(output)
    }

    /// Return a processed buffer to the pool
    pub fn return_buffer(&mut self, buffer: Vec<f32>) {
        self.output_pool.release(buffer);
    }

    /// Get buffer statistics
    pub fn stats(&self) -> PreprocessorStats {
        PreprocessorStats {
            input_available: self.input_buffer.available(),
            input_free_space: self.input_buffer.free_space(),
            buffers_in_use: self.output_pool.in_use(),
            sample_rate: self.sample_rate,
        }
    }

    /// Clear all buffers
    pub fn clear(&self) {
        self.input_buffer.clear();
    }
}

/// Preprocessor statistics
#[derive(Debug, Clone)]
pub struct PreprocessorStats {
    pub input_available: usize,
    pub input_free_space: usize,
    pub buffers_in_use: usize,
    pub sample_rate: u32,
}

// ============================================================================
// Voice Activity Detection (VAD)
// ============================================================================

/// Simple energy-based voice activity detector
pub struct VoiceActivityDetector {
    /// Energy threshold for speech
    threshold: f32,
    /// Smoothing factor for energy
    smoothing: f32,
    /// Current smoothed energy
    energy: f32,
    /// History of energy values
    history: Vec<f32>,
    /// History size
    history_size: usize,
    /// Consecutive speech frames
    speech_frames: u32,
    /// Consecutive silence frames
    silence_frames: u32,
    /// Minimum speech frames to trigger
    min_speech_frames: u32,
    /// Minimum silence frames to end
    min_silence_frames: u32,
}

impl VoiceActivityDetector {
    /// Create a new VAD
    pub fn new() -> Self {
        Self {
            threshold: 0.01,
            smoothing: 0.95,
            energy: 0.0,
            history: Vec::with_capacity(50),
            history_size: 50,
            speech_frames: 0,
            silence_frames: 0,
            min_speech_frames: 3,
            min_silence_frames: 15,
        }
    }

    /// Process a frame of audio and return speech detection result
    pub fn process(&mut self, samples: &[f32]) -> VadResult {
        // Calculate RMS energy with SIMD
        let frame_energy = calculate_rms_simd(samples);

        // Update smoothed energy
        self.energy = self.smoothing * self.energy + (1.0 - self.smoothing) * frame_energy;

        // Update history
        self.history.push(self.energy);
        if self.history.len() > self.history_size {
            self.history.remove(0);
        }

        // Adaptive threshold based on history
        let adaptive_threshold = if self.history.len() >= 10 {
            let min_energy: f32 = self.history.iter().cloned().fold(f32::MAX, f32::min);
            let max_energy: f32 = self.history.iter().cloned().fold(0.0f32, f32::max);
            min_energy + (max_energy - min_energy) * 0.3
        } else {
            self.threshold
        };

        let is_speech = self.energy > adaptive_threshold.max(self.threshold);

        // Update frame counters
        if is_speech {
            self.speech_frames += 1;
            self.silence_frames = 0;
        } else {
            self.silence_frames += 1;
            if self.silence_frames > self.min_silence_frames {
                self.speech_frames = 0;
            }
        }

        VadResult {
            is_speech,
            energy: self.energy,
            threshold: adaptive_threshold,
            speech_probability: if is_speech {
                (self.speech_frames as f32 / self.min_speech_frames as f32).min(1.0)
            } else {
                0.0
            },
            should_process: self.speech_frames >= self.min_speech_frames,
            end_of_speech: !is_speech && self.silence_frames >= self.min_silence_frames,
        }
    }

    /// Reset VAD state
    pub fn reset(&mut self) {
        self.energy = 0.0;
        self.history.clear();
        self.speech_frames = 0;
        self.silence_frames = 0;
    }
}

impl Default for VoiceActivityDetector {
    fn default() -> Self {
        Self::new()
    }
}

/// Voice activity detection result
#[derive(Debug, Clone)]
pub struct VadResult {
    /// Is current frame speech
    pub is_speech: bool,
    /// Current energy level
    pub energy: f32,
    /// Adaptive threshold
    pub threshold: f32,
    /// Speech probability (0.0-1.0)
    pub speech_probability: f32,
    /// Should trigger STT processing
    pub should_process: bool,
    /// End of speech detected
    pub end_of_speech: bool,
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_ring_buffer_basic() {
        let buffer: RingBuffer<i16> = RingBuffer::new(1024);

        // Write some data
        let samples = [1, 2, 3, 4, 5];
        let written = buffer.write(&samples);
        assert_eq!(written, 5);

        // Read it back
        let mut output = [0i16; 5];
        let read = buffer.read(&mut output);
        assert_eq!(read, 5);
        assert_eq!(output, samples);
    }

    #[test]
    fn test_ring_buffer_wrap() {
        let buffer: RingBuffer<i16> = RingBuffer::new(8); // 8 capacity

        // Write near end
        let samples1 = [1, 2, 3, 4, 5, 6];
        buffer.write(&samples1);

        // Read some
        let mut output = [0i16; 4];
        buffer.read(&mut output);

        // Write more (will wrap)
        let samples2 = [7, 8, 9, 10];
        let written = buffer.write(&samples2);
        assert_eq!(written, 4);

        // Read remaining
        let mut output2 = [0i16; 6];
        let read = buffer.read(&mut output2);
        assert_eq!(read, 6);
        assert_eq!(output2, [5, 6, 7, 8, 9, 10]);
    }

    #[test]
    fn test_buffer_pool() {
        let mut pool: BufferPool<f32> = BufferPool::new(4, 1024);

        // Acquire buffers
        let b1 = pool.acquire().unwrap();
        let b2 = pool.acquire().unwrap();
        assert_eq!(pool.in_use(), 2);

        // Release one
        pool.release(b1);
        assert_eq!(pool.in_use(), 1);

        // Acquire again (should reuse)
        let _b3 = pool.acquire().unwrap();
        assert_eq!(pool.in_use(), 2);
    }

    #[test]
    fn test_i16_to_f32_conversion() {
        let input: Vec<i16> = vec![0, 16384, -16384, 32767, -32768];
        let mut output = vec![0.0f32; 5];

        convert_i16_to_f32_simd(&input, &mut output);

        assert!((output[0] - 0.0).abs() < 0.001);
        assert!((output[1] - 0.5).abs() < 0.001);
        assert!((output[2] - -0.5).abs() < 0.001);
        assert!((output[3] - 1.0).abs() < 0.001);
        assert!((output[4] - -1.0).abs() < 0.001);
    }

    #[test]
    fn test_rms_calculation() {
        // DC signal should give constant RMS
        let dc_signal = vec![0.5f32; 1000];
        let rms = calculate_rms_simd(&dc_signal);
        assert!((rms - 0.5).abs() < 0.001);

        // Silence should give 0
        let silence = vec![0.0f32; 1000];
        let rms_silence = calculate_rms_simd(&silence);
        assert!(rms_silence < 0.001);
    }

    #[test]
    fn test_peak_finding() {
        let samples = vec![0.1f32, -0.5, 0.3, 0.8, -0.2];
        let peak = find_peak_simd(&samples);
        assert!((peak - 0.8).abs() < 0.001);
    }

    #[test]
    fn test_vad_basic() {
        let mut vad = VoiceActivityDetector::new();

        // Process silence
        let silence = vec![0.0f32; 160];
        let result = vad.process(&silence);
        assert!(!result.is_speech);

        // Process "speech" (loud signal)
        let speech = vec![0.5f32; 160];
        let result = vad.process(&speech);
        assert!(result.is_speech);
    }

    #[test]
    fn test_preprocessor() {
        let mut preprocessor = AudioPreprocessor::new(16000, 16000);

        // Write some samples
        let samples: Vec<i16> = (0..8000).map(|i| (i % 100 * 100) as i16).collect();
        preprocessor.write(&samples);

        let stats = preprocessor.stats();
        assert!(stats.input_available > 0);
    }
}

/*
 * Spark energizes. SIMD accelerates. Zero-copy minimizes latency.
 * Audio flows efficiently through optimized pipelines.
 *
 * h(x) >= 0. Always.
 */
