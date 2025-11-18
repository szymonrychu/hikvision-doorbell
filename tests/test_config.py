# import logging

# import kubernetes_dynamic as kd
# from kubernetes.client.exceptions import ApiException

# from hikvision_doorbell.config import (
#     load_config,
#     load_from_annotations,
#     load_from_kubernetes,
# )
# from hikvision_doorbell.utils import b64enc

# logger = logging.getLogger(__name__)


# class MockSecrets:
#     def get(self, secret_name: str, secret_namespace: str = None) -> kd.models.V1Secret:
#         if secret_name == "non_existent":
#             raise ApiException()
#         secret = kd.models.V1Secret()
#         secret.metadata.name = secret_name
#         secret.metadata.namespace = secret_namespace or "default"
#         if secret_name == "test_secret":
#             secret.data["proxy-allowed-groups"] = b64enc(secret_name)
#             secret.data["proxy-client-id"] = b64enc(secret_name)
#             secret.data["proxy-client-secret"] = b64enc(secret_name)
#             secret.data["proxy-redirect-url"] = b64enc(secret_name)
#             secret.data["proxy-cookie-domain"] = b64enc(secret_name)
#             secret.data["proxy-cookie-secret"] = b64enc(secret_name)
#         elif secret_name == "default_secret":
#             secret.data["proxy-container-image"] = b64enc(secret_name)
#             secret.data["proxy-container-image-pull-policy"] = b64enc(secret_name)
#             secret.data["proxy-container-tag"] = b64enc(secret_name)
#             secret.data["proxy-container-name"] = b64enc(secret_name)
#             secret.data["proxy-cookie-name"] = b64enc(secret_name)
#             secret.data["proxy-email-domains"] = b64enc(secret_name)
#             secret.data["proxy-http-port"] = b64enc(str(123))
#             secret.data["proxy-oidc-issuer-url"] = b64enc(secret_name)
#             secret.data["proxy-resources-requests-cpu"] = b64enc(secret_name)
#             secret.data["proxy-resources-requests-memory"] = b64enc(secret_name)
#             secret.data["proxy-resources-limits-cpu"] = b64enc(secret_name)
#             secret.data["proxy-resources-limits-memory"] = b64enc(secret_name)
#         return secret


# class MockClient:
#     def __init__(self):
#         self.secrets = MockSecrets()


# def test_load_from_kubernetes_name_empty():
#     mock_client = MockClient()

#     config = load_from_kubernetes(None, None, mock_client)
#     assert config is None


# def test_load_from_kubernetes_secret_not_exists():
#     mock_client = MockClient()

#     config = load_from_kubernetes("non_existent", None, mock_client)
#     assert config is None


# def test_load_from_kubernetes_secret_missing_fields():
#     mock_client = MockClient()

#     config = load_from_kubernetes("test_missing_fields", "test", mock_client)
#     assert not config.all_required_fields_set


# def test_load_from_kubernetes():
#     mock_client = MockClient()

#     config = load_from_kubernetes("test_secret", "test_secret", mock_client)

#     assert config is not None
#     assert config.proxy_container_name == "proxy"
#     assert config.proxy_provider == "keycloak-oidc"
#     assert config.proxy_http_port == 4180
#     assert config.proxy_email_domains == "*"
#     assert config.proxy_allowed_groups == "test_secret"
#     assert config.proxy_client_id == "test_secret"
#     assert config.proxy_client_secret == "test_secret"
#     assert config.proxy_redirect_url == "test_secret"
#     assert config.proxy_issuer_url is None
#     assert config.proxy_cookie_name is None
#     assert config.proxy_cookie_domain == "test_secret"
#     assert config.proxy_cookie_secret == "test_secret"
#     assert config.proxy_resources_requests_cpu == "100m"
#     assert config.proxy_resources_requests_memory == "128Mi"
#     assert config.proxy_resources_limits_cpu == "200m"
#     assert config.proxy_resources_limits_memory == "256Mi"
#     assert config.proxy_container_image == "quay.io/oauth2-proxy/oauth2-proxy"
#     assert config.proxy_container_tag == "v7.5.1"
#     assert config.proxy_container_image_pull_policy == "IfNotPresent"
#     assert config.patch_container_name is None
#     assert config.patch_port_number is None
#     assert config.patch_port_name is None
#     assert config.secret_name is None
#     assert config.secret_namespace is None
#     assert not config.all_required_fields_set


# def test_load_from_annotations():
#     test_pod = kd.models.V1Pod()
#     test_pod.metadata.annotations = {
#         "oauth2-proxy-admission/proxy-allowed-groups": "test_pod",
#         "oauth2-proxy-admission/proxy-client-id": "test_pod",
#         "oauth2-proxy-admission/proxy-client-secret": "test_pod",
#         "oauth2-proxy-admission/proxy-redirect-url": "test_pod",
#         "oauth2-proxy-admission/proxy-oidc-issuer-url": "test_pod",
#         "oauth2-proxy-admission/proxy-cookie-domain": "test_pod",
#         "oauth2-proxy-admission/proxy-cookie-secret": "test_pod",
#         "oauth2-proxy-admission/patch-container-name": "test_pod",
#         "oauth2-proxy-admission/patch-port-number": str(123),
#         "oauth2-proxy-admission/proxy-port-name": "test_pod",
#         "oauth2-proxy-admission/secret-name": "test_secret",
#         "oauth2-proxy-admission/secret-namespace": "test_secret",
#     }

#     config = load_from_annotations(test_pod)

#     assert config is not None
#     assert config.proxy_container_name == "proxy"
#     assert config.proxy_provider == "keycloak-oidc"
#     assert config.proxy_http_port == 4180
#     assert config.proxy_email_domains == "*"
#     assert config.proxy_allowed_groups == "test_pod"
#     assert config.proxy_client_id == "test_pod"
#     assert config.proxy_client_secret == "test_pod"
#     assert config.proxy_redirect_url == "test_pod"
#     assert config.proxy_issuer_url == "test_pod"
#     assert config.proxy_cookie_name is None
#     assert config.proxy_cookie_domain == "test_pod"
#     assert config.proxy_cookie_secret == "test_pod"
#     assert config.proxy_resources_requests_cpu == "100m"
#     assert config.proxy_resources_requests_memory == "128Mi"
#     assert config.proxy_resources_limits_cpu == "200m"
#     assert config.proxy_resources_limits_memory == "256Mi"
#     assert config.proxy_container_image == "quay.io/oauth2-proxy/oauth2-proxy"
#     assert config.proxy_container_tag == "v7.5.1"
#     assert config.proxy_container_image_pull_policy == "IfNotPresent"
#     assert config.patch_container_name == "test_pod"
#     assert config.patch_port_number == 123
#     assert config.patch_port_name == "test_pod"
#     assert config.secret_name == "test_secret"
#     assert config.secret_namespace == "test_secret"
#     assert not config.all_required_fields_set


# def test_load_config():
#     test_pod = kd.models.V1Pod()
#     test_pod.metadata.annotations = {
#         "oauth2-proxy-admission/secret-name": "test_secret",
#         "oauth2-proxy-admission/secret-namespace": "test_secret",
#         "oauth2-proxy-admission/patch-container-name": "test_annotations",
#     }
#     mock_client = MockClient()

#     config = load_config(test_pod, mock_client, "default_secret", "default_secret_namespace")

#     assert config is not None
#     assert config.proxy_container_name == "default_secret"
#     assert config.proxy_provider == "keycloak-oidc"
#     assert config.proxy_http_port == 123
#     assert config.proxy_email_domains == "default_secret"
#     assert config.proxy_allowed_groups == "test_secret"
#     assert config.proxy_client_id == "test_secret"
#     assert config.proxy_client_secret == "test_secret"
#     assert config.proxy_redirect_url == "test_secret"
#     assert config.proxy_issuer_url == "default_secret"
#     assert config.proxy_cookie_name == "default_secret"
#     assert config.proxy_cookie_domain == "test_secret"
#     assert config.proxy_cookie_secret == "test_secret"
#     assert config.proxy_resources_requests_cpu == "default_secret"
#     assert config.proxy_resources_requests_memory == "default_secret"
#     assert config.proxy_resources_limits_cpu == "default_secret"
#     assert config.proxy_resources_limits_memory == "default_secret"
#     assert config.proxy_container_image == "default_secret"
#     assert config.proxy_container_tag == "default_secret"
#     assert config.proxy_container_image_pull_policy == "default_secret"
#     assert config.patch_container_name == "test_annotations"
#     assert config.patch_port_number is None
#     assert config.patch_port_name is None
#     assert config.secret_name == "test_secret"
#     assert config.secret_namespace == "test_secret"
#     assert config.all_required_fields_set
