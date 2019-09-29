from koe.features import freq_domain, time_domain
from koe.features import linear_prediction
from koe.features import mt_features
from koe.features import other_features
from koe.features import scaled_freq_features
from koe.models import Feature

feature_extractors = {}
features = []
feature_map = {}

feature_whereabout = {
    freq_domain: [
        ('spectral_flatness', False, True),
        ('spectral_flux', False, True),
        ('spectral_bandwidth', False, True),
        ('spectral_centroid', False, True),
        ('spectral_contrast', False, False),
        ('spectral_rolloff', False, True),
        ('spectral_crest', False, True),
        ('spectral_skewness', False, True),
        ('spectral_kurtosis', False, True),
        ('spectral_decrease', False, True),
        ('harmonic_ratio', False, True),
        ('fundamental_frequency', False, True),
        ('spectrum', False, False),
        ('total_energy', True, True),
        ('aggregate_entropy', True, True),
        ('average_entropy', True, True),
        ('average_power', True, True),
        ('max_power', True, True),
        ('max_frequency', True, True),
        ('dominant_frequency', False, True),
    ],
    scaled_freq_features: [
        ('mfcc', False, False),
        ('mfc', False, False),
        ('mfcc_delta', False, False),
        ('mfcc_delta2', False, False),
    ],
    time_domain: [
        ('duration', True, True),
        ('zero_crossing_rate', False, True),
        ('log_attack_time', True, True),
        ('energy_envelope', False, True)
    ],
    mt_features: [
        ('frequency_modulation', False, True),
        ('amplitude_modulation', False, True),
        ('goodness_of_pitch', False, True),
        ('amplitude', False, True),  # TODO: Normalise
        ('entropy', False, True),
        ('mean_frequency', False, True),
        ('spectral_continuity', False, True)
    ],
    linear_prediction: [
        ('lpc_cepstrum', False, False),
        ('lp_coefficients', False, False)
    ],
    other_features: [
        ('frame_entropy', False, True),
        ('average_frame_power', False, True),
        ('max_frame_power', False, True),
        # ('s2s_autoencoded', True, False),
        ('mlp_autoencoded', True, True),
    ]
}


ftgroup_names = {
    'mfc': ['mfc'],
    'mfcc': ['mfcc'],
    'mfcc+': ['mfcc', 'mfcc_delta'],
    'mfcc++': ['mfcc', 'mfcc_delta', 'mfcc_delta2'],
    'mfcc_delta_only': ['mfcc_delta', 'mfcc_delta2'],
    'lpceps': ['lpc_cepstrum'],
    'lpcoefs': ['lp_coefficients'],
    'freq_domain': [
        'spectral_flatness', 'spectral_flux', 'spectral_bandwidth', 'spectral_centroid', 'spectral_contrast',
        'spectral_rolloff', 'spectral_crest', 'spectral_skewness', 'spectral_kurtosis', 'spectral_decrease',
        'harmonic_ratio', 'fundamental_frequency', 'dominant_frequency'
    ],
    'time_domain': [
        'duration', 'zero_crossing_rate', 'log_attack_time', 'energy_envelope'
    ],
    'mt_domain': [
        'frequency_modulation', 'amplitude_modulation', 'goodness_of_pitch', 'amplitude', 'entropy', 'mean_frequency',
        'spectral_continuity',
    ],
    'all': []
}


def init():
    for module, feature_names in feature_whereabout.items():
        for feature_name, is_fixed_length, is_one_dimensional in feature_names:
            feature = Feature.objects.filter(name=feature_name).first()
            if feature is None:
                feature = Feature(name=feature_name)
            feature.is_fixed_length = is_fixed_length
            feature.is_one_dimensional = is_one_dimensional
            feature.save()

            extractor = getattr(module, feature_name, None)
            feature_extractors[feature_name] = extractor
            features.append(feature)
            feature_map[feature_name] = feature
