const LANGS = {
  en: {
    _meta: { name: "English", dir: "ltr" },

    // Topbar
    projects: "projects",
    new_project: "+ new project",
    idle: "idle",

    // Projects drawer
    projects_title: "PROJECTS",
    no_projects: "No saved projects yet",
    save_current: "save current project",
    current: "current",
    meta_interviewee: "Interviewee",
    meta_date: "Recording date",
    meta_notes: "Notes",
    duplicate: "Duplicate",

    // Phase bar
    phase_interview: "Interview",
    phase_narration: "Narration (optional)",
    phase_assembly: "Assembly",

    // Phase 1: Transcript
    transcript_label: "TRANSCRIPT — select text to mark clips",
    upload_prompt: "Drag a WAV / MP3 file or click to select",
    upload_hint: "transcription via OpenAI Whisper",
    setup_intro: "Welcome! To get started, you'll need an OpenAI API key for transcription. A HuggingFace token is optional — it enables speaker detection.",
    setup_openai_hint: 'Get one at <a href="https://platform.openai.com/api-keys" target="_blank">platform.openai.com/api-keys</a>',
    setup_hf_hint: 'Get one at <a href="https://huggingface.co/settings/tokens" target="_blank">huggingface.co/settings/tokens</a> (Read permission). Also accept <a href="https://huggingface.co/pyannote/speaker-diarization-community-1" target="_blank">model terms</a>.',
    setup_optional: "(optional)",
    setup_save: "Save & Start",
    setup_openai_required: "OpenAI API key is required",
    setup_validating: "Validating keys…",
    setup_done: "API keys saved!",
    try_demo: "Try a demo interview",
    diarize_label: "Detect multiple speakers",
    diarize_hint: "adds ~1 min processing time",
    diarize_notice: "Speaker detection is approximate. Right-click a speaker badge to reassign.",
    badge_tooltip: "Click to rename · Right-click to reassign",
    clips_title: "CLIPS",
    clips_empty: "— select text in transcript to mark clips —",
    cut_clips: "✂ cut clips",
    download_clips_zip: "⬇ download clips (.zip)",
    download_transcript: "Download transcript (Word)",
    finish_narration: "finish phase — narration →",

    // Phase 2: Narration
    narration_label: "NARRATION — select text to mark clips",
    narration_empty: "— upload narration audio and transcribe to see text here —",
    script_title: "SCRIPT",
    script_placeholder: "Paste your narration script here (optional)…",
    import_script: "import script from .docx / .txt",
    narration_audio_title: "NARRATION AUDIO",
    upload_narration: "+ upload narration audio",
    replace_narration: "↻ replace narration audio",
    transcribe_narration: "▶ transcribe narration",
    narration_clips_title: "NARRATION CLIPS",
    cut_narration: "✂ cut narration clips",
    skip_assembly: "skip to assembly →",
    finish_assembly: "finish phase — assembly →",

    // Phase 3: Assembly
    assembly_label: "ASSEMBLY — drag clips to build rough cut",
    interview_clips: "INTERVIEW CLIPS",
    narration_clips: "NARRATION CLIPS",
    assemble: "▶ assemble rough cut",
    clear: "clear",
    save_project: "save project",
    export_folder: "export folder…",
    export_folder_set: "Export folder set",
    export_folder_cleared: "Export folder cleared",
    export_folder_current: "Current export folder:",
    export_folder_change: "OK to choose a new folder, Cancel to disable export.",
    export_folder_picking: "Choose a folder…",
    gap_label: "gap between clips",
    download_output: "⬇ download rough cut",
    reassemble: "↺ re-assemble",
    export_paper_edit: "export final transcript (.docx)",
    paper_edit_ready: "final transcript ready!",

    // Assembly empty states
    asm_empty: "drag clips and narration here to build the rough cut",
    asm_no_clips: "cut clips first",
    asm_no_narration: "no narration clips",

    // Selection toolbar
    play: "▶ play",
    mark_clip: "✂ mark clip",

    // Dialogs & prompts
    project_name_prompt: "Project name:",
    name_project_prompt: "Name this project:",
    save_before_new: "Save current project before starting a new one?",
    unsaved_warning: "Start a new project? Unsaved work will be lost.",
    load_confirm: 'Load project "{name}"? Current session will be replaced.',
    drag_first: "Drag items to the timeline first",

    // Status messages
    transcribing: "transcribing…",
    step_compress: "compressing",
    step_whisper: "transcribing",
    step_process: "processing",
    step_speakers: "speakers",
    transcribed: "transcribed · {count} passages",
    cutting_clips: "cutting clips…",
    clips_cut: "clips cut",
    importing_script: "importing script…",
    script_imported: "script imported",
    uploading_narration: "uploading narration…",
    narration_uploaded: "narration uploaded — add script then transcribe",
    transcribing_narration: "transcribing narration…",
    narration_transcribed: "narration transcribed — select text to mark clips",
    cutting_narration: "cutting narration…",
    narration_cut: "narration clips cut",
    assembling: "assembling…",
    rough_cut_ready: "rough cut ready!",
    server_error: "Server error",
    transcription_failed: "Transcription failed",

    // Project name
    untitled: "untitled",
    click_to_rename: "Click to rename",
    click_to_name: "Click to name this project",

    // Upload
    choose_file: "choose file",

    // Search
    search_placeholder: "Search transcript…",

    // Delete project
    delete_confirm: 'Delete project "{name}"? This cannot be undone.',

    // Misc
    passages: "passages",
    clips_word: "clips",
    no_file: "",
  },

  he: {
    _meta: { name: "עברית", dir: "rtl" },

    // Topbar
    projects: "פרויקטים",
    new_project: "+ פרויקט חדש",
    idle: "פנוי",

    // Projects drawer
    projects_title: "פרויקטים",
    no_projects: "אין פרויקטים שמורים",
    save_current: "שמור פרויקט נוכחי",
    current: "נוכחי",
    meta_interviewee: "מרואיין",
    meta_date: "תאריך הקלטה",
    meta_notes: "הערות",
    duplicate: "שכפל",

    // Phase bar
    phase_interview: "תמלול וחיתוך אינסרטים",
    phase_narration: "קריינות (אופציונלי)",
    phase_assembly: "הרכבת קובץ סופי",

    // Phase 1: Transcript
    transcript_label: "תמלול — סמן טקסט לסימון קליפים",
    upload_prompt: "גרור קובץ WAV / MP3 או לחץ לבחירה",
    upload_hint: "תמלול באמצעות OpenAI Whisper",
    setup_intro: "ברוכים הבאים! כדי להתחיל, תצטרכו מפתח API של OpenAI לתמלול. טוקן HuggingFace הוא אופציונלי — הוא מאפשר זיהוי דוברים.",
    setup_openai_hint: 'השיגו אחד ב-<a href="https://platform.openai.com/api-keys" target="_blank">platform.openai.com/api-keys</a>',
    setup_hf_hint: 'השיגו אחד ב-<a href="https://huggingface.co/settings/tokens" target="_blank">huggingface.co/settings/tokens</a> (הרשאת Read). גם אשרו את <a href="https://huggingface.co/pyannote/speaker-diarization-community-1" target="_blank">תנאי המודל</a>.',
    setup_optional: "(אופציונלי)",
    setup_save: "שמור והתחל",
    setup_openai_required: "מפתח API של OpenAI נדרש",
    setup_validating: "מאמת מפתחות…",
    setup_done: "מפתחות API נשמרו!",
    try_demo: "נסו ראיון לדוגמה",
    diarize_label: "זיהוי דוברים מרובים",
    diarize_hint: "מוסיף כדקה לזמן העיבוד",
    diarize_notice: "זיהוי הדוברים הוא משוער. לחיצה על כפתור עכבר ימני תשנה את שיוך הדובר.",
    badge_tooltip: "לחצו לשינוי שם · לחצו ימני לשינוי שיוך",
    clips_title: "קליפים",
    clips_empty: "— סמן טקסט בתמלול כדי ליצור קליפים —",
    cut_clips: "✂ חתוך קליפים",
    download_clips_zip: "⬇ הורד קליפים (.zip)",
    download_transcript: "הורד תמלול (Word)",
    finish_narration: "סיום שלב — קריינות ←",

    // Phase 2: Narration
    narration_label: "קריינות — סמן טקסט לסימון קליפים",
    narration_empty: "— העלה קובץ קריינות ותמלל כדי לראות טקסט כאן —",
    script_title: "תסריט",
    script_placeholder: "הדבק כאן את תסריט הקריינות (אופציונלי)…",
    import_script: "ייבוא תסריט מ-.docx / .txt",
    narration_audio_title: "קובץ קריינות",
    upload_narration: "+ העלה קובץ קריינות",
    replace_narration: "↻ החלף קובץ קריינות",
    transcribe_narration: "תמלל קריינות ◀",
    narration_clips_title: "קליפים מקריינות",
    cut_narration: "✂ חתוך קליפים מקריינות",
    skip_assembly: "דלג להרכבה ←",
    finish_assembly: "סיום שלב — הרכבה ←",

    // Phase 3: Assembly
    assembly_label: "הרכבה — גרור קליפים לבניית הקובץ השלם",
    interview_clips: "קליפים מראיון",
    narration_clips: "קליפים מקריינות",
    assemble: "הרכב קובץ שלם ◀",
    clear: "נקה",
    save_project: "שמור פרויקט",
    export_folder: "תיקיית ייצוא…",
    export_folder_set: "תיקיית ייצוא הוגדרה",
    export_folder_cleared: "תיקיית ייצוא בוטלה",
    export_folder_current: "תיקיית ייצוא נוכחית:",
    export_folder_change: "OK לבחירת תיקייה חדשה, Cancel לביטול ייצוא.",
    export_folder_picking: "בחרו תיקייה…",
    gap_label: "הפסקה בין קליפים",
    download_output: "הורידו קובץ סופי ⬇",
    reassemble: "↺ הרכב מחדש",
    export_paper_edit: "ייצוא תמלול סופי (.docx)",
    paper_edit_ready: "תמלול סופי מוכן!",

    // Assembly empty states
    asm_empty: "גרור קליפים וקריינות לכאן כדי לבנות את הקובץ השלם",
    asm_no_clips: "חתוך קליפים קודם",
    asm_no_narration: "אין קליפים מקריינות",

    // Selection toolbar
    play: "נגן ◀",
    mark_clip: "✂ סמן קליפ",

    // Dialogs & prompts
    project_name_prompt: "שם הפרויקט:",
    name_project_prompt: "תן שם לפרויקט:",
    save_before_new: "לשמור את הפרויקט הנוכחי לפני שמתחילים חדש?",
    unsaved_warning: "להתחיל פרויקט חדש? עבודה שלא נשמרה תאבד.",
    load_confirm: 'לטעון את הפרויקט "{name}"? הסשן הנוכחי יוחלף.',
    drag_first: "גרור פריטים לציר הזמן קודם",

    // Status messages
    transcribing: "מתמלל…",
    step_compress: "דחיסה",
    step_whisper: "תמלול",
    step_process: "עיבוד",
    step_speakers: "דוברים",
    transcribed: "תמלול הושלם · {count} קטעים",
    cutting_clips: "חותך קליפים…",
    clips_cut: "קליפים נחתכו",
    importing_script: "מייבא תסריט…",
    script_imported: "תסריט יובא",
    uploading_narration: "מעלה קריינות…",
    narration_uploaded: "קריינות הועלתה — הוסף תסריט ותמלל",
    transcribing_narration: "מתמלל קריינות…",
    narration_transcribed: "קריינות תומללה — סמן טקסט ליצירת קליפים",
    cutting_narration: "חותך קליפים מקריינות…",
    narration_cut: "קליפים מקריינות נחתכו",
    assembling: "מרכיב…",
    rough_cut_ready: "הקובץ השלם מוכנה!",
    server_error: "שגיאת שרת",
    transcription_failed: "התמלול נכשל",

    // Project name
    untitled: "ללא שם",
    click_to_rename: "לחץ לשינוי שם",
    click_to_name: "לחץ לתת שם לפרויקט",

    // Upload
    choose_file: "בחר קובץ",

    // Search
    search_placeholder: "חיפוש בתמלול…",

    // Delete project
    delete_confirm: 'למחוק את הפרויקט "{name}"? לא ניתן לבטל.',

    // Misc
    passages: "קטעים",
    clips_word: "קליפים",
    no_file: "",
  }
};
