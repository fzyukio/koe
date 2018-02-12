import json

__all__ = ['tables', 'actions']

tables_str = """
{
  "segment-info": {
    "class": "koe.Segment",
    "getter": "koe.bulk_get_segment_info",
    "columns": [
      {
        "name": "ID",
        "slug": "id",
        "type": "INTEGER",
        "is_attribute": true
      },
      {
        "name": "Start",
        "slug": "start_time_ms",
        "type": "INTEGER",
        "is_attribute": true
      },
      {
        "name": "End",
        "slug": "end_time_ms",
        "type": "INTEGER",
        "is_attribute": true
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
        "css_class": "has-image"
      },
      {
        "name": "Family",
        "slug": "label_family",
        "type": "SHORT_TEXT",
        "editable": true,
        "is_extra_attr": true,
        "editor": "Select",
        "css_class": "overflow"
      },
      {
        "name": "Subfamily",
        "slug": "label_subfamily",
        "type": "SHORT_TEXT",
        "editable": true,
        "is_extra_attr": true,
        "editor": "Select",
        "css_class": "overflow"
      },
      {
        "name": "Label",
        "slug": "label",
        "type": "SHORT_TEXT",
        "editable": true,
        "is_extra_attr": true,
        "editor": "Select",
        "css_class": "overflow"
      },
      {
        "name": "DTW distance",
        "slug": "distance",
        "type": "FLOAT"
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
        "editable": true,
        "is_extra_attr": true
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
        "is_attribute": true
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
        "editable": true,
        "is_extra_attr": true
      }
    ]
  }
}

"""
tables = json.loads(tables_str)


actions_str = """
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
"""

actions = json.loads(actions_str)
