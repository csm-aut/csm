
from constants import Platform

# The key has "-p" so it can also match 'asr9k-p/hfr-p' platforms

CRS_PACKAGES = {
    'hfr-asr9000v-nV-p': 'hfr-asr9000v-nV-px.pie',
    'hfr-diags-p': 'hfr-diags-px.pie',
    'hfr-doc-p': 'hfr-doc-px.pie',
    'hfr-fit-p': 'hfr-fit-px.pie',
    'hfr-fpd-p': 'hfr-fpd-px.pie',
    'hfr-infra-test-p': 'hfr-infra-test-px.pie',
    'hfr-k9sec-p': 'hfr-k9sec-px.pie',
    'hfr-li-p': 'hfr-li-px.pie',
    'hfr-mcast-p': 'hfr-mcast-px.pie',
    'hfr-mgbl-p': 'hfr-mgbl-px.pie',
    'hfr-mini-p': 'hfr-mini-px.pie',
    'hfr-mpls-p': 'hfr-mpls-px.pie',
    'hfr-pagent-p': 'hfr-pagent-px.pie',
    'hfr-services-p': 'hfr-services-px.pie',
    'hfr-upgrade-p': 'hfr-upgrade-px.pie',
    'hfr-video-p': 'hfr-video-px.pie'
}

       
ASR9K_PACKAGES = {
    'asr9k-9000v-nV-p': 'asr9k-asr9000v-nV-px.pie',
    'asr9k-asr901-nV-p': 'asr9k-asr901-nV-px.pie',
    'asr9k-asr903-nV-p': 'asr9k-asr903-nV-px.pie',
    'asr9k-bng-p': 'asr9k-bng-px.pie',
    'asr9k-doc-p': 'asr9k-doc-px.pie',
    'asr9k-fpd-p': 'asr9k-fpd-px.pie',
    'asr9k-infra-test-p': 'asr9k-infra-test-px.pie',
    'asr9k-k9sec-p': 'asr9k-k9sec-px.pie',
    'asr9k-li-p': 'asr9k-li-px.pie',
    'asr9k-mcast-p': 'asr9k-mcast-px.pie',
    'asr9k-mgbl-p': 'asr9k-mgbl-px.pie',
    'asr9k-mini-p': 'asr9k-mini-px.pie',
    'asr9k-mpls-p': 'asr9k-mpls-px.pie',
    'asr9k-optic-p': 'asr9k-optic-px.pie',
    'asr9k-services-infra': 'asr9k-services-infra-px.pie',
    'asr9k-services-p': 'asr9k-services-px.pie',
    'asr9k-video-p': 'asr9k-video-px.pie',
}

"""
If match_internal_name is true, it matches the host_packages instead of the physical name
on the server repository.
"""
def get_target_software_package_list(platform, host_packages, target_version, match_internal_name=False):
    target_list = []
    platform_package_list = {}
    
    if platform == Platform.ASR9K:
        platform_package_list = ASR9K_PACKAGES
    elif platform == Platform.CRS:
        platform_package_list = CRS_PACKAGES
        
    for k, v in platform_package_list.items():
        for package in host_packages:
            if k in package:
                if match_internal_name:
                    # FIXME: Works for ASR9K/CRS
                    if k.endswith('p'):
                        k += 'x'
                        
                    target_list.append("{}-{}".format(k, target_version))
                else:
                    target_list.append("{}-{}".format(v, target_version))
    
    return target_list