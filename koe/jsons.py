import json

__all__ = ['tables', 'actions']

tables = \
    {
        "segment-info": {
            "class": "koe.Segment",
            "getter": "koe.bulk_get_segment_info",
            "columns": [
                {
                    "slug": "_checkbox_selector",
                    "editable": False,
                    "is_addon": True
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
                    "type": "SHORT_TEXT"
                },
                {
                    "name": "Signal mask",
                    "slug": "signal_mask",
                    "type": "IMAGE",
                    "css_class": "has-image"
                },
                {
                    "name": "Spectrogram",
                    "slug": "spectrogram",
                    "type": "IMAGE",
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
                    "name": "DTW Index",
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
                },
                {
                    "name": "Mean FF",
                    "slug": "mean_ff",
                    "type": "FLOAT"
                },
                {
                    "name": "Min FF",
                    "slug": "min_ff",
                    "type": "FLOAT"
                },
                {
                    "name": "Max FF",
                    "slug": "max_ff",
                    "type": "FLOAT"
                },
            ]
        },
        "version-grid": {
            "class": "koe.HistoryEntry",
            "columns": [
                {
                    "slug": "_checkbox_selector",
                    "editable": False,
                    "is_addon": True
                },
                {
                    "name": "Created by",
                    "slug": "creator",
                    "type": "SHORT_TEXT"
                },
                {
                    "name": "Time",
                    "slug": "time",
                    "type": "SHORT_TEXT",
                    "is_attribute": True
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
                    "editable": True,
                    "is_extra_attr": True
                }
            ]
        }
    }

actions = \
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
