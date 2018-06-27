from koe.features import librosa_features, raven_features
from koe.features import mt_features
from koe.features import other_features
from koe.models import Feature

feature_extractors = {}
features = []
feature_map = {}

feature_whereabout = {
    librosa_features: [
        ('spectral_flatness', False, True),
        ('spectral_bandwidth', False, True),
        ('spectral_centroid', False, True),
        ('spectral_contrast', False, False),
        ('tonnetz', False, False),
        ('spectral_rolloff', False, True),
        ('chroma_stft', False, False),
        ('chroma_cqt', False, False),
        ('chroma_cens', False, False),
        ('mfcc', False, False),
        ('zero_crossing_rate', False, True),
    ],
    raven_features: [
        ('total_energy', True, True),
        ('aggregate_entropy', True, True),
        ('average_entropy', True, True),
        ('average_power', True, True),
        ('max_power', True, True),
        ('max_frequency', True, True),
    ],
    mt_features: [
        # ('time_derivative', False, False),
        # ('freq_derivative', False, False),
        ('frequency_modulation', False, True),
        ('amplitude_modulation', False, True),
        ('goodness_of_pitch', False, True),
        # ('mtspect', False, False),
        ('amplitude', False, True),  # TODO: Normalise
        ('entropy', False, True),
        # ('frequency_contours', False, False),
        ('mean_frequency', False, True),
        # ('spectral_derivative', False, False),
        ('spectral_continuity', False, True)
    ],
    other_features: [
        ('duration', True, True),
        ('frame_entropy', False, True),
        ('average_frame_power', False, True),
        ('max_frame_power', False, True),
        ('dominant_frequency', False, True),
    ]
}

for module, feature_names in feature_whereabout.items():
    for feature_name, is_fixed_length, is_one_dimensional in feature_names:
        feature = Feature.objects.get_or_create(name=feature_name, is_fixed_length=is_fixed_length,
                                                is_one_dimensional=is_one_dimensional)[0]

        extractor = getattr(module, feature_name)
        feature_extractors[feature_name] = extractor
        features.append(feature)
        feature_map[feature_name] = feature
