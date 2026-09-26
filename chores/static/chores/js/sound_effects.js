// chores/static/chores/js/sound_effects.js

function playSound(type) {
    try {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (!AudioContext) return;
        const ctx = new AudioContext();
        const now = ctx.currentTime;
        
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        
        osc.type = 'sine';
        
        if (type === 'coin') {
            // Quick happy 'ding'
            osc.frequency.setValueAtTime(1046.50, now); // C6
            osc.frequency.setValueAtTime(1318.51, now + 0.1); // E6
            gain.gain.setValueAtTime(0, now);
            gain.gain.linearRampToValueAtTime(0.3, now + 0.05);
            gain.gain.exponentialRampToValueAtTime(0.01, now + 0.4);
            osc.start(now);
            osc.stop(now + 0.4);
        } 
        else if (type === 'task') {
            // Joyful ascending chime
            osc.frequency.setValueAtTime(523.25, now); // C5
            osc.frequency.setValueAtTime(659.25, now + 0.1); // E5
            osc.frequency.setValueAtTime(783.99, now + 0.2); // G5
            osc.frequency.setValueAtTime(1046.50, now + 0.3); // C6
            gain.gain.setValueAtTime(0, now);
            gain.gain.linearRampToValueAtTime(0.2, now + 0.05);
            gain.gain.exponentialRampToValueAtTime(0.01, now + 0.6);
            osc.start(now);
            osc.stop(now + 0.6);
        }
        else if (type === 'reward') {
            // Triumphant magical jingle
            osc.type = 'triangle';
            osc.frequency.setValueAtTime(587.33, now);      // D5
            osc.frequency.setValueAtTime(739.99, now + 0.1);  // F#5
            osc.frequency.setValueAtTime(880.00, now + 0.2);  // A5
            osc.frequency.setValueAtTime(1174.66, now + 0.3); // D6
            gain.gain.setValueAtTime(0, now);
            gain.gain.linearRampToValueAtTime(0.25, now + 0.05);
            gain.gain.exponentialRampToValueAtTime(0.01, now + 0.65);
            osc.start(now);
            osc.stop(now + 0.65);
        }
        else if (type === 'purchase') {
            // Two-tone register purchase chime
            osc.frequency.setValueAtTime(783.99, now);       // G5
            osc.frequency.setValueAtTime(1046.50, now + 0.12); // C6
            osc.frequency.setValueAtTime(1567.98, now + 0.22); // G6
            gain.gain.setValueAtTime(0, now);
            gain.gain.linearRampToValueAtTime(0.25, now + 0.04);
            gain.gain.exponentialRampToValueAtTime(0.01, now + 0.55);
            osc.start(now);
            osc.stop(now + 0.55);
        }
        else if (type === 'correct') {
            // Bright cheerful ascending chime (A5 to E6)
            osc.type = 'sine';
            osc.frequency.setValueAtTime(880.00, now);       // A5
            osc.frequency.setValueAtTime(1318.51, now + 0.1);  // E6
            gain.gain.setValueAtTime(0, now);
            gain.gain.linearRampToValueAtTime(0.25, now + 0.04);
            gain.gain.exponentialRampToValueAtTime(0.01, now + 0.45);
            osc.start(now);
            osc.stop(now + 0.45);
        }
        else if (type === 'incorrect') {
            // Gentle soft descending tone (E5 to C5)
            osc.type = 'triangle';
            osc.frequency.setValueAtTime(659.25, now);       // E5
            osc.frequency.setValueAtTime(523.25, now + 0.15);  // C5
            gain.gain.setValueAtTime(0, now);
            gain.gain.linearRampToValueAtTime(0.2, now + 0.04);
            gain.gain.exponentialRampToValueAtTime(0.01, now + 0.35);
            osc.start(now);
            osc.stop(now + 0.35);
        }
    } catch (e) {}
}

function playAndSubmit(event, type) {
    event.preventDefault();
    const form = event.target;
    playSound(type);
    setTimeout(() => {
        form.submit();
    }, 400);
}

function playAndNavigate(event, type, url) {
    event.preventDefault();
    playSound(type);
    setTimeout(() => {
        window.location.href = url;
    }, 400);
}