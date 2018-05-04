__all__ = ['tables', 'actions', 'num_exemplars']

tables = \
    {
        "segment-info": {
            "class": "koe.Segment",
            "getter": "koe.bulk_get_segment_info",
            "columns": [
                {
                    "slug": "_sel",
                    "editable": False,
                    "is_addon": True,
                    "type": "BOOLEAN"
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
                    "type": "BOOLEAN"
                },
                {
                    "name": "Filename",
                    "slug": "url",
                    "type": "URL"
                },
                {
                    "name": "Duration (msec)",
                    "slug": "duration",
                    "type": "INTEGER"
                },
                {
                    "name": "Date",
                    "slug": "date",
                    "type": "DATE"
                },
                {
                    "name": "Gender",
                    "slug": "gender",
                    "type": "SHORT_TEXT"
                },
                {
                    "name": "Species",
                    "slug": "species",
                    "type": "SHORT_TEXT"
                },
                {
                    "name": "Quality",
                    "slug": "quality",
                    "type": "SHORT_TEXT"
                },
                {
                    "name": "Individual",
                    "slug": "individual",
                    "type": "SHORT_TEXT"
                },
                {
                    "name": "Track",
                    "slug": "track",
                    "type": "SHORT_TEXT"
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
                    "type": "BOOLEAN"
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
                }
            ]
        },
    }

num_exemplars = 10
exemplars_grid_columns = tables['exemplars-grid']['columns']

for i in range(1, num_exemplars + 1):
    exemplars_grid_columns.append(
        {
            "name": "Exemplar {} Mask".format(i),
            "slug": "exemplar{}_mask".format(i),
            "type": "IMAGE",
            "css_class": "has-image"
        }
    )

for i in range(1, num_exemplars + 1):
    exemplars_grid_columns.append(
        {
            "name": "Exemplar {} Spectrogram".format(i),
            "slug": "exemplar{}_spect".format(i),
            "type": "IMAGE",
            "css_class": "has-image"
        }
    )

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
