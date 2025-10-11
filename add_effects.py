#!/usr/bin/env python3
"""
Interactive multi-band beat-synced video effects
IMPROVED VERSION - Better high frequency effect
"""

import librosa
import numpy as np
import subprocess
import sys
import os

def detect_frequency_beats(video_file, 
                          bass_range=(20, 200), 
                          mid_range=(200, 2000), 
                          high_range=(4000, 8000)):
    """Detect beats in specific frequency ranges"""
    print(f"🎵 Analyzing audio from {video_file}...")
    print(f"   Bass: {bass_range[0]}-{bass_range[1]} Hz")
    print(f"   Mid: {mid_range[0]}-{mid_range[1]} Hz")
    print(f"   High: {high_range[0]}-{high_range[1]} Hz")
    
    y, sr = librosa.load(video_file, sr=22050)
    
    # Split into frequency bands using bandpass
    D = librosa.stft(y)
    freqs = librosa.fft_frequencies(sr=sr)
    
    # Bass filter
    bass_mask = (freqs >= bass_range[0]) & (freqs <= bass_range[1])
    D_bass = D.copy()
    D_bass[~bass_mask, :] = 0
    y_bass = librosa.istft(D_bass)
    
    # Mid filter
    mid_mask = (freqs >= mid_range[0]) & (freqs <= mid_range[1])
    D_mid = D.copy()
    D_mid[~mid_mask, :] = 0
    y_mid = librosa.istft(D_mid)
    
    # High filter (narrower band)
    high_mask = (freqs >= high_range[0]) & (freqs <= high_range[1])
    D_high = D.copy()
    D_high[~high_mask, :] = 0
    y_high = librosa.istft(D_high)
    
    # Detect onsets in each band
    bass_onsets = librosa.onset.onset_detect(y=y_bass, sr=sr, units='time', 
                                              hop_length=512, backtrack=True)
    mid_onsets = librosa.onset.onset_detect(y=y_mid, sr=sr, units='time',
                                             hop_length=256, backtrack=True)
    high_onsets = librosa.onset.onset_detect(y=y_high, sr=sr, units='time',
                                              hop_length=128, backtrack=True,
                                              pre_max=3, post_max=3,
                                              pre_avg=3, post_avg=3,
                                              delta=0.2, wait=10)
    
    print(f"✓ Bass onsets: {len(bass_onsets)}")
    print(f"✓ Mid onsets: {len(mid_onsets)}")
    print(f"✓ High onsets: {len(high_onsets)}")
    
    return {
        'bass': bass_onsets,
        'mid': mid_onsets,
        'high': high_onsets
    }

def make_between_expression(times, duration):
    """Create between() expressions for exact beat times"""
    if len(times) == 0:
        return "0"
    
    conditions = [f"between(t,{t:.3f},{t+duration:.3f})" for t in times]
    return "+".join(conditions)

def apply_bass_zoom(input_file, output_file, bass_times, zoom_amount=0.70, duration=0.15):
    """Apply zoom effect on actual bass hits"""
    
    enable_expr = make_between_expression(bass_times, duration)
    
    filter_str = (
        f"[0:v]negate=enable='{enable_expr}'[inverted];"
        f"[0:v]crop=iw*{zoom_amount}:ih*{zoom_amount}:(iw-iw*{zoom_amount})/2:(ih-ih*{zoom_amount})/2,scale=1280:720[zoomed];"
        f"[inverted][zoomed]overlay=enable='{enable_expr}'"
    )
    
    cmd = [
        'ffmpeg', '-i', input_file,
        '-filter_complex', filter_str,
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
        '-c:a', 'copy',
        '-y', output_file
    ]
    
    result = subprocess.run(cmd)
    return result.returncode == 0

def apply_mid_saturation(input_file, output_file, mid_times, saturation=2.0, duration=0.08):
    """Apply color saturation on actual mid hits"""
    
    if len(mid_times) == 0:
        subprocess.run(['cp', input_file, output_file])
        return True
    
    conditions = [f"between(t,{t:.3f},{t+duration:.3f})" for t in mid_times]
    enable_expr = "+".join(conditions)
    
    filter_str = f"hue=s='if({enable_expr},{saturation},1)'"
    
    cmd = [
        'ffmpeg', '-i', input_file,
        '-vf', filter_str,
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
        '-c:a', 'copy',
        '-y', output_file
    ]
    
    result = subprocess.run(cmd)
    return result.returncode == 0

def apply_high_effect(input_file, output_file, high_times, effect_type='vignette', intensity=0.5, duration=0.10):
    """Apply visible effect on actual high hits - with multiple effect options"""
    
    if len(high_times) == 0:
        subprocess.run(['cp', input_file, output_file])
        return True
    
    conditions = [f"between(t,{t:.3f},{t+duration:.3f})" for t in high_times]
    enable_expr = "+".join(conditions)
    
    # Choose effect type
    if effect_type == 'vignette':
        # Vignette flash (darkens edges)
        vignette_strength = intensity * 0.8  # 0-0.8 range
        filter_str = f"vignette=angle='if({enable_expr},PI/2,0)':mode=forward"
        
    elif effect_type == 'tint':
        # White tint overlay
        tint_opacity = intensity * 0.5  # 0-0.5 range
        filter_str = f"drawbox=enable='{enable_expr}':x=0:y=0:w=iw:h=ih:color=white@{tint_opacity}:t=fill"
        
    elif effect_type == 'sharpen':
        # Sharpen effect
        sharpen_amount = 5 + (intensity * 10)  # 5-15 range
        filter_str = f"unsharp=enable='{enable_expr}':la={sharpen_amount}:ca={sharpen_amount}"
        
    elif effect_type == 'edges':
        # Edge glow effect - simpler approach
        # Apply edge detection and blend it as white lines
        filter_str = f"edgedetect=low=0.1:high=0.3:mode=colormix,hue=s=0,eq=brightness=0.3,negate=enable='{enable_expr}'"
    
    elif effect_type == 'invert':
        # Invert colors for dramatic flash (more visible than just desaturating)
        filter_str = f"negate=enable='{enable_expr}'"
        
    elif effect_type == 'radial':
        # Radial zoom flash
        zoom_factor = 1 + (intensity * 0.15)  # 1.0-1.15
        filter_str = f"zoompan=z='if({enable_expr},{zoom_factor},1)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
    
    else:  # 'flash' - improved brightness/contrast
        brightness = intensity * 0.5  # 0-0.5
        contrast = 1 + (intensity * 2)  # 1-3
        filter_str = f"eq=brightness='if({enable_expr},{brightness},0)':contrast='if({enable_expr},{contrast},1)'"
    
    # All effects now use simple -vf
    cmd = [
        'ffmpeg', '-i', input_file,
        '-vf', filter_str,
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
        '-c:a', 'copy',
        '-y', output_file
    ]
    
    result = subprocess.run(cmd)
    return result.returncode == 0

def interactive_bass_layer(input_file, output_file, bass_times):
    """Interactive refinement of bass zoom effect"""
    print("\n" + "="*60)
    print("🔊 BASS LAYER (Zoom Effect)")
    print("="*60)
    
    zoom_amount = 0.70
    duration = 0.15
    max_beats = 5000  # Increased from 100!
    
    while True:
        print(f"\n⚙️  Current settings:")
        print(f"   Detected bass hits: {len(bass_times)}")
        print(f"   Using first: {min(len(bass_times), max_beats)} beats")
        print(f"   Zoom amount: {zoom_amount:.2f} (lower = bigger zoom)")
        print(f"   Duration: {duration:.2f}s per hit")
        
        choice = input("\n👉 (r)ender / (z)oom / (d)uration / (m)ax beats / (s)kip / (q)uit: ").lower().strip()
        
        if choice == 'r':
            print(f"\n🎬 Rendering bass layer...\n")
            times_to_use = bass_times[:max_beats]
            success = apply_bass_zoom(input_file, output_file, times_to_use, zoom_amount, duration)
            if success:
                print(f"\n✓ Preview saved: {output_file}")
                print(f"   Watch it, then come back!")
            else:
                print(f"\n❌ Rendering failed!")
                continue
        elif choice == 's':
            print("⏭️  Skipping bass layer")
            subprocess.run(['cp', input_file, output_file])
            break
        elif choice == 'q':
            sys.exit(0)
        elif choice == 'z':
            new_zoom = input(f"   Enter zoom (0.5=huge, 0.9=small) [current: {zoom_amount:.2f}]: ")
            if new_zoom:
                zoom_amount = float(new_zoom)
        elif choice == 'd':
            new_dur = input(f"   Enter duration in seconds [current: {duration:.2f}]: ")
            if new_dur:
                duration = float(new_dur)
        elif choice == 'm':
            new_max = input(f"   Max beats to use [current: {max_beats}]: ")
            if new_max:
                max_beats = int(new_max)
        
        if choice == 'r' and success:
            lock = input("\n👉 Happy? (y)es = lock in / (n)o = adjust: ").lower().strip()
            if lock == 'y':
                print("✓ Bass layer locked in!")
                break

def interactive_mid_layer(input_file, output_file, mid_times):
    """Interactive refinement of mid saturation effect"""
    print("\n" + "="*60)
    print("🎨 MID LAYER (Color Saturation)")
    print("="*60)
    
    saturation = 2.0
    duration = 0.08
    max_beats = 5000  # Increased from 150!
    
    while True:
        print(f"\n⚙️  Current settings:")
        print(f"   Detected mid hits: {len(mid_times)}")
        print(f"   Using first: {min(len(mid_times), max_beats)} beats")
        print(f"   Saturation: {saturation:.1f}")
        print(f"   Duration: {duration:.2f}s per hit")
        
        choice = input("\n👉 (r)ender / (s)aturation / (d)uration / (m)ax beats / (k)ip / (q)uit: ").lower().strip()
        
        if choice == 'r':
            print(f"\n🎬 Rendering mid layer...\n")
            times_to_use = mid_times[:max_beats]
            success = apply_mid_saturation(input_file, output_file, times_to_use, saturation, duration)
            if success:
                print(f"\n✓ Preview saved: {output_file}")
            else:
                print(f"\n❌ Rendering failed!")
                continue
        elif choice == 'k':
            print("⏭️  Skipping mid layer")
            subprocess.run(['cp', input_file, output_file])
            break
        elif choice == 'q':
            sys.exit(0)
        elif choice == 's':
            new_sat = input(f"   Enter saturation [current: {saturation:.1f}]: ")
            if new_sat:
                saturation = float(new_sat)
        elif choice == 'd':
            new_dur = input(f"   Enter duration [current: {duration:.2f}]: ")
            if new_dur:
                duration = float(new_dur)
        elif choice == 'm':
            new_max = input(f"   Max beats to use [current: {max_beats}]: ")
            if new_max:
                max_beats = int(new_max)
        
        if choice == 'r' and success:
            lock = input("\n👉 Happy? (y)es / (n)o: ").lower().strip()
            if lock == 'y':
                print("✓ Mid layer locked in!")
                break

def interactive_high_layer(input_file, output_file, high_times):
    """Interactive refinement of high effect - with multiple effect types!"""
    print("\n" + "="*60)
    print("⚡ HIGH LAYER (Multiple Effect Options)")
    print("="*60)
    
    effect_type = 'tint'  # Default to tint (visible!)
    intensity = 0.7
    duration = 0.10
    max_beats = 5000  # Increased from 100!
    
    print("\n📋 Available effects:")
    print("   tint      - White color overlay (RECOMMENDED)")
    print("   vignette  - Edge darkening flash")
    print("   invert    - Color inversion flash (very visible!)")
    print("   edges     - Edge glow effect")
    print("   sharpen   - Sharpness boost")
    print("   radial    - Subtle zoom")
    print("   flash     - Brightness (original, subtle)")
    
    while True:
        print(f"\n⚙️  Current settings:")
        print(f"   Detected high hits: {len(high_times)}")
        print(f"   Using first: {min(len(high_times), max_beats)} beats")
        print(f"   Effect type: {effect_type}")
        print(f"   Intensity: {intensity:.2f} (0.0-1.0)")
        print(f"   Duration: {duration:.2f}s per hit")
        
        choice = input("\n👉 (r)ender / (e)ffect / (i)ntensity / (d)uration / (m)ax beats / (s)kip / (q)uit: ").lower().strip()
        
        if choice == 'r':
            print(f"\n🎬 Rendering high layer with '{effect_type}' effect...\n")
            times_to_use = high_times[:max_beats]
            success = apply_high_effect(input_file, output_file, times_to_use, effect_type, intensity, duration)
            if success:
                print(f"\n✓ Final video saved: {output_file}")
            else:
                print(f"\n❌ Rendering failed!")
                continue
        elif choice == 's':
            print("⏭️  Skipping high layer")
            subprocess.run(['cp', input_file, output_file])
            break
        elif choice == 'q':
            sys.exit(0)
        elif choice == 'e':
            print("\n   Choose effect:")
            print("   1=tint  2=vignette  3=invert  4=edges  5=sharpen  6=radial  7=flash")
            effect_choice = input("   Enter number or name: ").lower().strip()
            effect_map = {
                '1': 'tint', 'tint': 'tint',
                '2': 'vignette', 'vignette': 'vignette',
                '3': 'invert', 'invert': 'invert',
                '4': 'edges', 'edges': 'edges',
                '5': 'sharpen', 'sharpen': 'sharpen',
                '6': 'radial', 'radial': 'radial',
                '7': 'flash', 'flash': 'flash'
            }
            if effect_choice in effect_map:
                effect_type = effect_map[effect_choice]
                print(f"   ✓ Effect set to: {effect_type}")
        elif choice == 'i':
            new_intensity = input(f"   Enter intensity (0.0-1.0) [current: {intensity:.2f}]: ")
            if new_intensity:
                intensity = float(new_intensity)
        elif choice == 'd':
            new_dur = input(f"   Enter duration [current: {duration:.2f}]: ")
            if new_dur:
                duration = float(new_dur)
        elif choice == 'm':
            new_max = input(f"   Max beats to use [current: {max_beats}]: ")
            if new_max:
                max_beats = int(new_max)
        
        if choice == 'r' and success:
            lock = input("\n👉 Happy? (y)es = FINISH / (n)o: ").lower().strip()
            if lock == 'y':
                print("✓ High layer locked in!")
                break

def main():
    if len(sys.argv) < 2:
        print("Usage: python lola_beat_improved.py <video.mp4>")
        print("\nOptional: Specify frequency ranges")
        print("python lola_beat_improved.py video.mp4 <bass_low> <bass_high> <mid_low> <mid_high> <high_low> <high_high>")
        sys.exit(1)
    
    video_file = sys.argv[1]
    base_name = os.path.splitext(video_file)[0]
    
    # Parse frequency ranges if provided
    if len(sys.argv) >= 8:
        bass_range = (int(sys.argv[2]), int(sys.argv[3]))
        mid_range = (int(sys.argv[4]), int(sys.argv[5]))
        high_range = (int(sys.argv[6]), int(sys.argv[7]))
    else:
        bass_range = (20, 200)
        mid_range = (200, 2000)
        high_range = (4000, 8000)
    
    bass_output = f"{base_name}_01_bass.mp4"
    mid_output = f"{base_name}_02_mid.mp4"
    final_output = f"{base_name}_03_final.mp4"
    
    # Detect beats in frequency bands
    beats = detect_frequency_beats(video_file, bass_range, mid_range, high_range)
    
    # Interactive layers with ACTUAL beat times
    interactive_bass_layer(video_file, bass_output, beats['bass'])
    interactive_mid_layer(bass_output, mid_output, beats['mid'])
    interactive_high_layer(mid_output, final_output, beats['high'])
    
    print("\n" + "="*60)
    print("✨ ALL DONE!")
    print("="*60)
    print(f"Final video: {final_output}")
    print(f"\n💡 TIP: To adjust frequency ranges, run:")
    print(f"python lola_beat_improved.py {video_file} 20 200 200 2000 6000 10000")

if __name__ == '__main__':
    main()
