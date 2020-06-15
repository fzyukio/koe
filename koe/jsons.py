__all__ = ['tables', 'actions']

tables =\
    {
        "segment-info": {
            "class": "koe.Segment",
            "getter": "koe.bulk_get_segment_info",
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
                    "type": "FLOAT",
                    "is_attribute": True
                },
                {
                    "name": "End",
                    "slug": "end_time_ms",
                    "type": "FLOAT",
                    "is_attribute": True
                },
                {
                    "name": "Duration",
                    "slug": "duration",
                    "type": "FLOAT"
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
                    "name": "Similarity Index",
                    "slug": "sim_index",
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
                    "name": "Song added",
                    "slug": "song_added",
                    "type": "DATE",
                },
                {
                    "name": "Date of record",
                    "slug": "record_date",
                    "type": "DATE"
                },
                {
                    "name": "Sex",
                    "slug": "sex",
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
                    "editable": True
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
                    "slug": "class",
                    "type": "SHORT_TEXT"
                },
                {
                    "name": "Count",
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
                    "name": "Added",
                    "slug": "added",
                    "type": "DATE",
                    "editable": False,
                    "is_attribute": True,
                },
                {
                    "name": "Date of record",
                    "slug": "record_date",
                    "type": "DATE",
                    "editable": True,
                    "is_attribute": False,
                },
                {
                    "name": "Sex",
                    "slug": "sex",
                    "type": "SHORT_TEXT",
                    "editable": True,
                    "is_attribute": True,
                    "setter": "set_gender"
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
                    "type": "FLOAT",
                    "is_attribute": True
                },
                {
                    "name": "End",
                    "slug": "end",
                    "type": "FLOAT",
                    "is_attribute": True
                },
                {
                    "name": "Duration",
                    "slug": "duration",
                    "type": "FLOAT"
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
                    "type": "FLOAT"
                },
                {
                    "name": "End",
                    "slug": "end",
                    "type": "FLOAT"
                },
                {
                    "name": "Duration",
                    "slug": "duration",
                    "type": "FLOAT"
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
                    "name": "Sex",
                    "slug": "gender",
                    "type": "SHORT_TEXT",
                    "editable": True,
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
                # {
                #     "name": "Accumulated occurrences",
                #     "slug": "accumoccurs",
                #     "type": "INTEGER"
                # },
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
                    "name": "Association Rule",
                    "slug": "assocrule",
                    "type": "SHORT_TEXT",
                }
            ]
        },
        "database-grid": {
            "class": "koe.Database",
            "getter": "koe.bulk_get_database",
            "filter": True,
            "columns": [
                {
                    "name": "Name",
                    "slug": "name",
                    "type": "SHORT_TEXT",
                    "is_attribute": True,
                    "editable": True,
                },
                {
                    "name": "Permission",
                    "slug": "permission",
                    "type": "SHORT_TEXT",
                    "editable": False
                },
                {
                    "name": "FFT Window",
                    "slug": "nfft",
                    "type": "INTEGER",
                    "is_attribute": True,
                    "editable": True
                },
                {
                    "name": "Overlap",
                    "slug": "noverlap",
                    "type": "INTEGER",
                    "is_attribute": True,
                    "editable": True
                },
                {
                    "name": "Low Pass Filter",
                    "slug": "lpf",
                    "type": "INTEGER",
                    "is_attribute": True,
                    "editable": True
                },
                {
                    "name": "High Pass Filter",
                    "slug": "hpf",
                    "type": "INTEGER",
                    "is_attribute": True,
                    "editable": True
                }
            ]
        },

        "collection-grid": {
            "class": "koe.TemporaryDatabase",
            "getter": "koe.bulk_get_collection",
            "filter": True,
            "columns": [
                {
                    "name": "Name",
                    "slug": "name",
                    "type": "SHORT_TEXT",
                    "is_attribute": True,
                    "editable": True,
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
                    "editable": True
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
                    "type": "FLOAT",
                    "is_attribute": True
                },
                {
                    "name": "End",
                    "slug": "end_time_ms",
                    "type": "FLOAT",
                    "is_attribute": True
                },
                {
                    "name": "Duration",
                    "slug": "duration",
                    "type": "FLOAT"
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
        },
        "syntax-grid": {
            "class": "koe.AudioFile",
            "getter": "koe.get_syntactically_similar_pairs",
            "filter": True,
            "columns": [
                {
                    "name": "Class 1",
                    "slug": "class-1-name",
                    "type": "SHORT_TEXT"
                },
                {
                    "name": "Class 1 count",
                    "slug": "class-1-count",
                    "type": "INTEGER"
                },
                {
                    "name": "Class 2",
                    "slug": "class-2-name",
                    "type": "SHORT_TEXT"
                },
                {
                    "name": "Class 2 count",
                    "slug": "class-2-count",
                    "type": "INTEGER"
                },
                {
                    "name": "Distance (syntax)",
                    "slug": "syntax-distance",
                    "type": "FLOAT"
                },
                {
                    "name": "Distance (acoustic)",
                    "slug": "acoustic-distance",
                    "type": "FLOAT"
                },
                {
                    "name": "Weighted distance",
                    "slug": "weighted-distance",
                    "type": "FLOAT"
                }
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
