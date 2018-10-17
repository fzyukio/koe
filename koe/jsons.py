__all__ = ['tables', 'actions']

tables =\
    {
        "segment-info": {
            "class": "koe.Segment",
            "getter": "koe.bulk_get_segment_info",
            "editable": 'koe.validate_editability',
            "columns": [
                {
                    "slug": "_sel",
                    "editable": False,
                    "is_addon": True,
                    "type": "BOOLEAN",
                    "exportable": False,
                    "importable": False,
                },
                {
                    "name": "ID",
                    "slug": "id",
                    "type": "INTEGER",
                    "is_attribute": True
                },
                {
                    "name": "Start",
                    "slug": "start_time_ms",
                    "type": "INTEGER",
                    "is_attribute": True
                },
                {
                    "name": "End",
                    "slug": "end_time_ms",
                    "type": "INTEGER",
                    "is_attribute": True
                },
                {
                    "name": "Duration",
                    "slug": "duration",
                    "type": "INTEGER"
                },
                {
                    "name": "Song",
                    "slug": "song",
                    "type": "URL"
                },
                {
                    "name": "Spectrogram",
                    "slug": "spectrogram",
                    "type": "IMAGE",
                    "formatter": "Spect",
                    "css_class": "has-image"
                },
                {
                    "name": "Family",
                    "slug": "label_family",
                    "type": "SHORT_TEXT",
                    "editable": True,
                    "is_extra_attr": True,
                    "editor": "Select",
                    "css_class": "overflow"
                },
                {
                    "name": "Subfamily",
                    "slug": "label_subfamily",
                    "type": "SHORT_TEXT",
                    "editable": True,
                    "is_extra_attr": True,
                    "editor": "Select",
                    "css_class": "overflow"
                },
                {
                    "name": "Label",
                    "slug": "label",
                    "type": "SHORT_TEXT",
                    "editable": True,
                    "is_extra_attr": True,
                    "editor": "Select",
                    "css_class": "overflow"
                },
                {
                    "name": "Dendrogram Index",
                    "slug": "dtw_index",
                    "type": "INTEGER"
                },
                {
                    "name": "Note",
                    "slug": "note",
                    "type": "SHORT_TEXT",
                    "editable": True,
                    "is_extra_attr": True
                },
                {
                    "name": "Song note",
                    "slug": "song_note",
                    "type": "SHORT_TEXT"
                },
                {
                    "name": "Date",
                    "slug": "song_date",
                    "type": "DATE"
                },
                {
                    "name": "Gender",
                    "slug": "song_gender",
                    "type": "SHORT_TEXT"
                },
                {
                    "name": "Quality",
                    "slug": "song_quality",
                    "type": "SHORT_TEXT"
                },
                {
                    "name": "Individual",
                    "slug": "song_individual",
                    "type": "SHORT_TEXT"
                },
                {
                    "name": "Track",
                    "slug": "song_track",
                    "type": "SHORT_TEXT"
                }
            ]
        },
        "version-grid": {
            "class": "koe.HistoryEntry",
            "getter": "koe.bulk_get_history_entries",
            "columns": [
                {
                    "name": "Created by",
                    "slug": "creator",
                    "type": "SHORT_TEXT"
                },
                {
                    "name": "Time",
                    "slug": "time",
                    "type": "SHORT_TEXT"
                },
                {
                    "name": "Downloadable Link",
                    "slug": "url",
                    "type": "URL"
                },
                {
                    "name": "Note",
                    "slug": "note",
                    "type": "SHORT_TEXT",
                    "is_attribute": True,
                    "editable": "editability_validation"
                },
                {
                    "name": "Format version",
                    "slug": "version",
                    "type": "INTEGER"
                },
                {
                    "name": "Backup type",
                    "slug": "type",
                    "type": "SHORT_TEXT"
                },
                {
                    "name": "Database",
                    "slug": "database",
                    "type": "SHORT_TEXT"
                },
                {
                    "name": "Size (kb)",
                    "slug": "size",
                    "type": "FLOAT"
                }
            ]
        },
        "exemplars-grid": {
            "class": "koe.Segment",
            "getter": "koe.bulk_get_exemplars",
            "columns": [
                {
                    "name": "Class",
                    "slug": "cls",
                    "type": "SHORT_TEXT"
                },
                {
                    "name": "Exemplar count",
                    "slug": "count",
                    "type": "INTEGER"
                },
                {
                    "name": "Spectrograms",
                    "slug": "spectrograms",
                    "type": "IMAGE",
                    "formatter": "Spects",
                    "css_class": "has-images"
                }
            ]
        },
        "songs-grid": {
            "class": "koe.AudioFile",
            "getter": "koe.bulk_get_song_sequences",
            "editable": 'koe.validate_editability',
            "columns": [
                {
                    "slug": "_sel",
                    "editable": False,
                    "is_addon": True,
                    "type": "BOOLEAN",
                    "exportable": False,
                    "importable": False,
                },
                {
                    "name": "Filename",
                    "slug": "filename",
                    "type": "URL",
                    "exportable": True,
                    "importable": False,
                },
                {
                    "name": "Duration (msec)",
                    "slug": "duration",
                    "type": "INTEGER",
                    "importable": False,
                },
                {
                    "name": "Date",
                    "slug": "date",
                    "type": "DATE",
                    "editable": True,
                    "is_attribute": True,
                },
                {
                    "name": "Sex",
                    "slug": "gender",
                    "type": "SHORT_TEXT",
                    "editable": True,
                    "is_attribute": True,
                },
                {
                    "name": "Species",
                    "slug": "species",
                    "type": "SHORT_TEXT",
                    "editor": "Select",
                    "editable": True,
                    "is_attribute": True,
                    "css_class": "overflow"
                },
                {
                    "name": "Quality",
                    "slug": "quality",
                    "type": "SHORT_TEXT",
                    "editable": True,
                    "is_attribute": True,
                },
                {
                    "name": "Individual",
                    "slug": "individual",
                    "type": "SHORT_TEXT",
                    "editor": "Select",
                    "editable": True,
                    "is_attribute": True,
                    "css_class": "overflow"
                },
                {
                    "name": "Track",
                    "slug": "track",
                    "type": "SHORT_TEXT",
                    "editor": "Select",
                    "editable": True,
                    "is_attribute": True,
                    "css_class": "overflow"
                },
                {
                    "name": "Sequence",
                    "slug": "sequence",
                    "type": "SEQUENCE",
                    "css_class": "has-sequence"
                },
                {
                    "name": "Type",
                    "slug": "type",
                    "type": "SHORT_TEXT",
                    "editable": True,
                    "is_extra_attr": True,
                    "editor": "Select",
                    "css_class": "overflow"
                },
                {
                    "name": "Note",
                    "slug": "note",
                    "type": "LONG_TEXT",
                    "editable": True,
                    "is_extra_attr": True,
                    "css_class": "overflow"
                }
            ]
        },
        "segments-grid": {
            "class": "koe.Segment",
            "getter": "koe.bulk_get_segments_for_audio",
            "editable": 'koe.validate_editability',
            "columns": [
                {
                    "slug": "_sel",
                    "editable": False,
                    "is_addon": True,
                    "type": "BOOLEAN",
                    "exportable": False,
                    "importable": False,
                },
                {
                    "name": "ID",
                    "slug": "id",
                    "type": "INTEGER",
                    "is_attribute": True
                },
                {
                    "name": "Start",
                    "slug": "start",
                    "type": "INTEGER",
                    "is_attribute": True
                },
                {
                    "name": "End",
                    "slug": "end",
                    "type": "INTEGER",
                    "is_attribute": True
                },
                {
                    "name": "Duration",
                    "slug": "duration",
                    "type": "INTEGER"
                },
                {
                    "name": "Family",
                    "slug": "label_family",
                    "type": "SHORT_TEXT",
                    "editable": True,
                    "is_extra_attr": True,
                    "editor": "Select",
                    "css_class": "overflow"
                },
                {
                    "name": "Subfamily",
                    "slug": "label_subfamily",
                    "type": "SHORT_TEXT",
                    "editable": True,
                    "is_extra_attr": True,
                    "editor": "Select",
                    "css_class": "overflow"
                },
                {
                    "name": "Label",
                    "slug": "label",
                    "type": "SHORT_TEXT",
                    "editable": True,
                    "is_extra_attr": True,
                    "editor": "Select",
                    "css_class": "overflow"
                },
                {
                    "name": "Note",
                    "slug": "note",
                    "type": "SHORT_TEXT",
                    "editable": True,
                    "is_extra_attr": True
                },
            ]
        },
        "song-partition-grid": {
            "class": "koe.AudioFile",
            "getter": "koe.bulk_get_audio_file_for_raw_recording",
            "columns": [
                {
                    "slug": "_sel",
                    "editable": False,
                    "is_addon": True,
                    "type": "BOOLEAN",
                    "exportable": False,
                    "importable": False,
                },
                {
                    "name": "Upload progress",
                    "slug": "progress",
                    "type": "SHORT_TEXT"
                },
                {
                    "name": "Start",
                    "slug": "start",
                    "type": "INTEGER"
                },
                {
                    "name": "End",
                    "slug": "end",
                    "type": "INTEGER"
                },
                {
                    "name": "Duration",
                    "slug": "duration",
                    "type": "INTEGER"
                },
                {
                    "name": "Song name",
                    "slug": "name",
                    "type": "SHORT_TEXT",
                    "editable": True,
                    "is_attribute": True
                },
                {
                    "name": "Quality",
                    "slug": "quality",
                    "type": "SHORT_TEXT",
                    "editable": True,
                    "is_attribute": True
                },
                {
                    "name": "Individual",
                    "slug": "individual",
                    "type": "SHORT_TEXT",
                    "editable": True,
                    "is_attribute": True
                },
                {
                    "name": "Type",
                    "slug": "type",
                    "type": "SHORT_TEXT",
                    "editable": True,
                    "is_extra_attr": True
                },
                {
                    "name": "Note",
                    "slug": "note",
                    "type": "LONG_TEXT",
                    "editable": True,
                    "is_extra_attr": True
                }
            ]
        },
        "sequence-mining-grid": {
            "class": "koe.AudioFile",
            "getter": "koe.bulk_get_song_sequence_associations",
            "columns": [
                {
                    "name": "Chain length",
                    "slug": "chainlength",
                    "type": "INTEGER"
                },
                {
                    "name": "Trans count",
                    "slug": "transcount",
                    "type": "INTEGER"
                },
                {
                    "name": "Accumulated occurrences",
                    "slug": "accumoccurs",
                    "type": "INTEGER"
                },
                {
                    "name": "Support",
                    "slug": "support",
                    "type": "FLOAT"
                },
                {
                    "name": "Confidence",
                    "slug": "confidence",
                    "type": "FLOAT"
                },
                {
                    "name": "Lift",
                    "slug": "lift",
                    "type": "FLOAT"
                },
                {
                    "name": "Assocociation Rule",
                    "slug": "assocrule",
                    "type": "SHORT_TEXT",
                }
            ]
        },
        "database-grid": {
            "class": "koe.Database",
            "getter": "koe.bulk_get_database",
            "columns": [
                {
                    "name": "Name",
                    "slug": "name",
                    "type": "SHORT_TEXT",
                    "editable": 'editability_validation',
                    "is_attribute": True
                },
                {
                    "name": "Permission",
                    "slug": "permission",
                    "type": "SHORT_TEXT"
                }
            ]
        },
        "database-assignment-grid": {
            "class": "koe.DatabaseAssignment",
            "getter": "koe.bulk_get_database_assignment",
            "columns": [
                {
                    "name": "Username",
                    "slug": "username",
                    "type": "SHORT_TEXT"
                },
                {
                    "name": "Permission",
                    "slug": "permission",
                    "type": "SHORT_TEXT",
                    "editor": "Select",
                    "formatter": "Select",
                    "choices": "koe.DatabasePermission",
                    "css_class": "overflow",
                    "is_attribute": True,
                    "editable": "editability_validation"
                }
            ]
        },
        "concise-syllables-grid": {
            "class": "koe.Segment",
            "getter": "koe.bulk_get_concise_segment_info",
            "columns": [
                {
                    "name": "Start",
                    "slug": "start_time_ms",
                    "type": "INTEGER",
                    "is_attribute": True
                },
                {
                    "name": "End",
                    "slug": "end_time_ms",
                    "type": "INTEGER",
                    "is_attribute": True
                },
                {
                    "name": "Duration",
                    "slug": "duration",
                    "type": "INTEGER"
                },
                {
                    "name": "Song",
                    "slug": "song",
                    "type": "SHORT_TEXT"
                },
                {
                    "name": "Spectrogram",
                    "slug": "spectrogram",
                    "type": "IMAGE",
                    "formatter": "Spect",
                    "css_class": "has-image"
                },
                {
                    "name": "Family",
                    "slug": "label_family",
                    "type": "SHORT_TEXT"
                },
                {
                    "name": "Subfamily",
                    "slug": "label_subfamily",
                    "type": "SHORT_TEXT"
                },
                {
                    "name": "Label",
                    "slug": "label",
                    "type": "SHORT_TEXT"
                },
            ]
        }
    }

actions =\
    {
        "reorder-columns": {
            "name": "Arrange row",
            "type": "INTEGER",
            "target": "VALUES_GRID"
        },
        "set-column-width": {
            "name": "Set Column Width",
            "type": "FLOAT",
            "target": "VALUES_GRID"
        }
    }
