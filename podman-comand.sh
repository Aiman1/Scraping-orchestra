podman pull gcr.io/google.com/cloudsdktool/google-cloud-cli:latest

podman run -ti --name gcloud-config gcr.io/google.com/cloudsdktool/google-cloud-cli gcloud init
podman run -ti --name gcloud-config gcr.io/google.com/cloudsdktool/google-cloud-cli gcloud auth login


podman run --rm --volumes-from gcloud-config gcr.io/google.com/cloudsdktool/google-cloud-cli gcloud projects list
podman run --rm --volumes-from gcloud-config gcr.io/google.com/cloudsdktool/google-cloud-cli gcloud compute instances list --project prefab-mile-237211


podman run --rm --volumes-from gcloud-config gcr.io/google.com/cloudsdktool/google-cloud-cli gcloud app deploy --region=eu-west1


podman run --rm --volumes-from gcloud-config gcr.io/google.com/cloudsdktool/google-cloud-cli gcloud app deploy 


podman run --it --volumes-from gcloud-config gcr.io/google.com/cloudsdktool/google-cloud-cli