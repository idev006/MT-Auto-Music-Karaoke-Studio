# Karaoke display object and preset catalog

## Separation of truth
`LyricsRevision` owns approved text, `LyricsTimeline` owns segment/tokens and timing. `KaraokeDisplayObject` owns how lyrics render; `Preset` supplies versioned property defaults. Updating style must not rerun alignment. `KaraokeLayout` and `Renderer` share text measurement and capability validation.

## Target property schema — 14 groups / 84 fields
| Group | Count | Properties |
|---|---:|---|
| P01 Identity/Lifecycle | 6 | object_id, object_name, object_type, enabled, locked, schema_version |
| P02 Geometry/Position | 8 | x, y, width, height, anchor, rotation, opacity, z_index |
| P03 Responsive Layout | 6 | layout_mode, safe_margin, padding, horizontal_alignment, vertical_alignment, aspect_policy |
| P04 Typography | 9 | font_family, font_asset_id, font_size, font_weight, font_style, letter_spacing, line_spacing, text_transform, language |
| P05 Text Arrangement | 6 | max_lines, wrap_mode, overflow_policy, line_break_policy, segment_spacing, text_direction |
| P06 Color/Highlight | 7 | inactive_color, active_color, completed_color, highlight_mode, highlight_direction, highlight_opacity, highlight_gradient |
| P07 Background/Container | 6 | background_enabled, background_color, background_opacity, border_radius, border, background_padding |
| P08 Effects/Readability | 6 | outline_width, outline_color, shadow_color, shadow_offset, shadow_blur, glow |
| P09 Timing/Sync | 7 | timeline_id, timeline_revision, sync_offset_ms, pre_roll_ms, post_roll_ms, timing_precision_ms, sync_policy |
| P10 Animation | 6 | enter_animation, exit_animation, enter_duration_ms, exit_duration_ms, animation_easing, keyframes |
| P11 Karaoke Behavior | 6 | display_mode, line_alternation, next_line_preview, instrumental_behavior, repeat_handling, highlight_completion |
| P12 Renderer | 5 | render_backend, render_quality, font_fallback_policy, color_space, render_scale |
| P13 Preview/Interaction | 3 | selectable, show_guides, preview_mode |
| P14 Accessibility/QA | 3 | minimum_font_size, minimum_contrast_ratio, quality_policy |

Use normalized geometry 0–1 with explicit reference coordinate rules. SSOT retains original Thai lyrics; presentation numeral policy converts displayed decimal digits to ASCII without mutating sources. Keyframing allowed only on whitelisted style/position fields, never IDs/revisions.

## Preset catalog — target 8 x 5 = 40
| Group | Five planned presets |
|---|---|
| Classic Karaoke | Classic Gold; Classic Blue; Retro Yellow; Traditional White; Dual-Line Classic |
| Modern Minimal | Pure White; Soft Shadow; Mono Clean; Floating Lyrics; Elegant Thin |
| Neon & Cyber | Electric Blue; Cyber Pink; Neon Green; Holographic; Dual Neon |
| Cinematic & Luxury | Royal Gold; Sapphire; Platinum; Executive Navy; Film Subtitle |
| Pop & Energetic | Pop Bounce; Candy Color; Summer Beat; Festival; Bold Rhythm |
| Romantic & Soft | Rose Glow; Pastel Dream; Soft Lavender; Warm Sunset; Gentle Pearl |
| Corporate & Official | Corporate Blue; Official White; Institutional Gold; Leadership; Formal Lower Third |
| High Readability | Maximum Contrast; Large Text; Strong Outline; Dark Caption Bar; Universal Readable |

## Implemented MVP catalog

The renderer currently ships 12 immutable presets across six groups: Classic (`classic-gold`,
`classic-blue`), Modern (`modern-minimal`, `glass-caption`), Neon (`neon-pink`, `neon-blue`),
Romantic (`romantic-rose`, `sunset-love`), Fun (`candy-pop`, `festival-bold`) and Accessible
(`maximum-contrast`, `dark-caption-bar`). Each preset has schema version 1 and a deterministic
content SHA-256 recorded in the run manifest. `list-presets` exposes the catalog and
`produce-song --karaoke-preset <preset-id>` selects one without changing canonical lyrics or any
timeline field. The remaining target catalog is backlog and must be released only with Thai
typography and preview/final parity evidence.

## Creative ownership
Creative Director sets style; Music Video Director sets motion/emotional intent; Motion Designer and Thai Typography Specialist specify look/readability; Rendering Engineer verifies engine parity; QA approves test renders. These are design responsibilities, not claims of hired staff.

## Preset rules
- Engine defaults -> immutable built-in preset -> job override -> supported time/keyframe override.
- Versioned preset_id, schema_version, content hash and renderer feature requirements.
- Built-in presets read-only; user presets clone and override; no silent unsupported effects.
- Release library in stages 8 -> 24 -> 40, not 40 untested variants at once.
- Validate safe area, combining marks, number display, contrast and preview-final parity with frame evidence.
