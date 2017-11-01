import os

from flask import abort, request, send_from_directory
from flask_restful import Resource
from flask_jwt_extended import jwt_required

from zou.app.services import (
    shots_service,
    files_service,
    persons_service,
    assets_service,
    projects_service,
    tasks_service,
    user_service
)
from zou.app.utils import thumbnail as thumbnail_utils, permissions


class CreatePreviewFilePictureResource(Resource):

    @jwt_required
    def post(self, instance_id):
        if not self.is_exist(instance_id):
            abort(404)

        if not self.is_allowed(instance_id):
            abort(403)

        uploaded_file = request.files["file"]
        folder_path = thumbnail_utils.get_preview_folder_name(
            "originals",
            instance_id
        )
        thumbnail_utils.save_file(
            folder_path,
            instance_id,
            uploaded_file,
            size=None
        )
        thumbnail_utils.generate_preview_variants(instance_id)

        return thumbnail_utils.get_preview_url_path(instance_id), 201

    def is_allowed(self, preview_file_id):
        if permissions.has_manager_permissions():
            return True
        else:
            preview_file = files_service.get_preview_file(preview_file_id)
            return user_service.check_assigned(preview_file.task_id)

    def is_exist(self, preview_file_id):
        return files_service.get_preview_file(preview_file_id) is not None


class BasePreviewPictureResource(Resource):

    def __init__(self, subfolder):
        Resource.__init__(self)
        self.subfolder = subfolder

    def is_exist(self, preview_file_id):
        return files_service.get_preview_file(preview_file_id) is not None

    def is_allowed(self, preview_file_id):
        if permissions.has_manager_permissions():
            return True
        else:
            preview_file = files_service.get_preview_file(preview_file_id)
            task = tasks_service.get_task(preview_file.task_id)
            return user_service.has_task_related(task["project_id"])

    @jwt_required
    def get(self, instance_id):
        if not self.is_exist(instance_id):
            abort(404)

        if not self.is_allowed():
            abort(403)

        folder_path = thumbnail_utils.get_preview_folder_name(
            self.subfolder,
            instance_id
        )
        file_name = thumbnail_utils.get_file_name(instance_id)

        # Use legacy folder name if the file cannot be found.
        if not os.path.exists(os.path.join(folder_path, file_name)):
            folder_path = thumbnail_utils.get_folder_name("preview-files")

        return send_from_directory(
            directory=folder_path,
            filename=file_name
        )


class PreviewFileThumbnailResource(BasePreviewPictureResource):

    def __init__(self):
        BasePreviewPictureResource.__init__(self, "thumbnails")


class PreviewFilePreviewResource(BasePreviewPictureResource):

    def __init__(self):
        BasePreviewPictureResource.__init__(self, "previews")


class PreviewFileThumbnailSquareResource(BasePreviewPictureResource):

    def __init__(self):
        BasePreviewPictureResource.__init__(
            self,
            "thumbnails-square"
        )


class PreviewFileOriginalResource(BasePreviewPictureResource):

    def __init__(self):
        BasePreviewPictureResource.__init__(self, "originals")


class BaseCreatePictureResource(Resource):

    def __init__(self, data_type, size=thumbnail_utils.RECTANGLE_SIZE):
        Resource.__init__(self)
        self.data_type = data_type
        self.size = size

    def check_permissions():
        permissions.check_admin_permissions()

    @jwt_required
    def post(self, instance_id):
        if not self.is_exist(instance_id):
            abort(404)

        try:
            self.check_permissions(instance_id)
            uploaded_file = request.files["file"]
            thumbnail_utils.save_file(
                self.data_type,
                instance_id,
                uploaded_file,
                size=self.size
            )

            thumbnail_url_path = \
                thumbnail_utils.url_path(
                    self.data_type,
                    instance_id
                )

            result = {"thumbnail_path": thumbnail_url_path}
        except permissions.PermissionDenied:
            abort(403)

        return result, 201


class BasePictureResource(Resource):

    def __init__(self, subfolder):
        Resource.__init__(self)
        self.subfolder = subfolder

    def is_allowed(self, instance_id):
        return True

    @jwt_required
    def get(self, instance_id):
        if not self.is_exist(instance_id):
            abort(404)

        if not self.is_allowed(instance_id):
            abort(403)

        return send_from_directory(
            directory=thumbnail_utils.get_folder_name(self.subfolder),
            filename=thumbnail_utils.get_file_name(instance_id)
        )


class CreatePersonThumbnailResource(BaseCreatePictureResource):

    def __init__(self):
        BaseCreatePictureResource.__init__(
            self,
            "persons",
            thumbnail_utils.SQUARE_SIZE
        )

    def is_exist(self, person_id):
        return persons_service.get_person(person_id) is not None

    def check_permissions(instance_id):
        is_current_user = persons_service.get_current_user().id != instance_id
        if is_current_user and not permissions.has_manager_permissions():
            raise permissions.PermissionDenied


class PersonThumbnailResource(BasePictureResource):

    def __init__(self):
        BasePictureResource.__init__(
            self,
            "persons"
        )

    def is_exist(self, person_id):
        return persons_service.get_person(person_id) is not None


class CreateProjectThumbnailResource(BaseCreatePictureResource):

    def __init__(self):
        BaseCreatePictureResource.__init__(
            self,
            "projects",
            thumbnail_utils.SQUARE_SIZE
        )

    def is_exist(self, project_id):
        return projects_service.get_project(project_id) is not None


class ProjectThumbnailResource(BasePictureResource):

    def __init__(self):
        BasePictureResource.__init__(self, "projects")

    def is_exist(self, project_id):
        return projects_service.get_project(project_id) is not None

    def is_allowed(self, project_id):
        try:
            if not permissions.has_manager_permissions():
                user_service.check_has_task_related(project_id)
            return True
        except permissions.PermissionDenied:
            return False


class CreateShotThumbnailResource(BaseCreatePictureResource):

    def __init__(self):
        BaseCreatePictureResource.__init__(self, "shots")

    def is_exist(self, shot_id):
        return shots_service.get_shot(shot_id) is not None


class ShotThumbnailResource(BasePictureResource):

    def __init__(self):
        BasePictureResource.__init__(self, "shots")

    def is_exist(self, shot_id):
        return shots_service.get_shot(shot_id) is not None

    def is_allowed(self, shot_id):
        shot = shots_service.get_shot(shot_id)
        try:
            if not permissions.has_manager_permissions():
                user_service.check_has_task_related(shot.project_id)
            return True
        except permissions.PermissionDenied:
            return False


class CreateAssetThumbnailResource(BaseCreatePictureResource):

    def __init__(self):
        BaseCreatePictureResource.__init__(self, "assets")

    def is_exist(self, asset_id):
        return assets_service.get_asset(asset_id) is not None


class AssetThumbnailResource(BasePictureResource):

    def __init__(self):
        BasePictureResource.__init__(self, "assets")

    def is_exist(self, asset_id):
        return assets_service.get_asset(asset_id) is not None

    def is_allowed(self, asset_id):
        asset = assets_service.get_asset(asset_id)
        try:
            if not permissions.has_manager_permissions():
                user_service.check_has_task_related(asset.project_id)
            return True
        except permissions.PermissionDenied:
            return False


class CreateWorkingFileThumbnailResource(BaseCreatePictureResource):

    def __init__(self):
        BaseCreatePictureResource.__init__(self, "working_files")

    def is_exist(self, working_file_id):
        return files_service.get_working_file(working_file_id) is not None


class WorkingFileThumbnailResource(BasePictureResource):

    def __init__(self):
        BasePictureResource.__init__(self, "working_files")

    def is_exist(self, working_file_id):
        return files_service.get_working_file(working_file_id) is not None

    def is_allowed(self, working_file_id):
        working_file = files_service.get_working_file(working_file_id)
        task = tasks_service.get_task(working_file.task_id)
        try:
            if not permissions.has_manager_permissions():
                user_service.check_has_task_related(task.project_id)
            return True
        except permissions.PermissionDenied:
            return False