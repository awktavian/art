/**
 * Audio feedback for 111/100 Crystal polish
 * 
 * Subtle sounds for key moments.
 */

export class AudioFeedback {
  private audioContext: AudioContext | null = null;
  private enabled: boolean = true;
  
  constructor() {
    // Create on first interaction (autoplay policy)
    document.addEventListener('click', () => this.init(), { once: true });
  }
  
  private init(): void {
    if (!this.audioContext) {
      this.audioContext = new AudioContext();
    }
  }
  
  /**
   * Play consensus reached sound
   */
  playConsensus(approved: boolean): void {
    if (!this.enabled || !this.audioContext) return;
    
    const ctx = this.audioContext;
    const now = ctx.currentTime;
    
    if (approved) {
      // Success: ascending major chord
      this.playTone(523.25, now, 0.1, 0.15); // C5
      this.playTone(659.25, now + 0.05, 0.1, 0.15); // E5
      this.playTone(783.99, now + 0.1, 0.2, 0.2); // G5
    } else {
      // Rejection: descending minor
      this.playTone(440.00, now, 0.1, 0.1); // A4
      this.playTone(392.00, now + 0.05, 0.15, 0.1); // G4
    }
  }
  
  /**
   * Play agent activity sound
   */
  playAgentActivity(): void {
    if (!this.enabled || !this.audioContext) return;
    
    const ctx = this.audioContext;
    const now = ctx.currentTime;
    
    // Subtle click
    this.playTone(800, now, 0.02, 0.05);
  }
  
  /**
   * Play vote cast sound
   */
  playVote(approve: boolean): void {
    if (!this.enabled || !this.audioContext) return;
    
    const ctx = this.audioContext;
    const now = ctx.currentTime;
    
    // Approve: up, Reject: down
    const freq = approve ? 600 : 400;
    this.playTone(freq, now, 0.05, 0.08);
  }
  
  private playTone(
    frequency: number,
    startTime: number,
    duration: number,
    volume: number = 0.1
  ): void {
    if (!this.audioContext) return;
    
    const ctx = this.audioContext;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    
    osc.connect(gain);
    gain.connect(ctx.destination);
    
    osc.frequency.value = frequency;
    osc.type = 'sine';
    
    // Envelope
    gain.gain.setValueAtTime(0, startTime);
    gain.gain.linearRampToValueAtTime(volume, startTime + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.001, startTime + duration);
    
    osc.start(startTime);
    osc.stop(startTime + duration);
  }
  
  setEnabled(enabled: boolean): void {
    this.enabled = enabled;
  }
  
  destroy(): void {
    if (this.audioContext) {
      this.audioContext.close();
    }
  }
}
