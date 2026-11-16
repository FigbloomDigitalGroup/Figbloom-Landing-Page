import logging

from rest_framework import serializers

from .models import Activity

logger = logging.getLogger(__name__)

COVER_MAX_BYTES = 5 * 1024 * 1024


def delete_stored_file(storage, name):
    """Remove an image from storage (local disk or Cloudinary).

    Takes the storage and file name rather than a FieldFile: FieldFile.delete()
    also blanks the field on the model instance, which is wrong when the
    instance has just been given a replacement image. A failure here must never
    undo the edit the admin just saved, so it's logged, not raised.
    """
    if not name:
        return

    try:
        storage.delete(name)
    except Exception:
        logger.warning('Could not delete activity image %s', name, exc_info=True)


class ActivityAdminSerializer(serializers.ModelSerializer):
    """What the dashboard reads and writes. Staff-only (see the viewset)."""

    category_label = serializers.CharField(read_only=True)
    image_url = serializers.SerializerMethodField()
    public_url = serializers.CharField(source='get_absolute_url', read_only=True)
    # Ticked in the form to drop the current cover image without uploading a
    # new one. Write-only: it isn't a column, just an instruction.
    remove_image = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = Activity
        fields = [
            'id',
            'title',
            'slug',
            'category',
            'category_label',
            'summary',
            'content',
            'activity_date',
            'location',
            'cover_image',
            'remove_image',
            'image_url',
            'public_url',
            'is_featured',
            'is_published',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at']
        extra_kwargs = {
            # Reads go through image_url (an absolute address that works for
            # both local disk and Cloudinary); this field is for uploads only.
            'cover_image': {'write_only': True, 'required': False, 'allow_null': True},
        }

    def get_image_url(self, obj):
        if not obj.cover_image:
            return ''

        url = obj.cover_image.url
        request = self.context.get('request')

        if request and not url.startswith(('http://', 'https://')):
            return request.build_absolute_uri(url)

        return url

    def validate_title(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError('A title is required.')

        return value

    def validate_summary(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError('A short summary is required.')

        return value

    def validate_cover_image(self, value):
        # ImageField has already confirmed it's a real, decodable image
        # (which also rules out SVG, a script-carrying format).
        if value and value.size > COVER_MAX_BYTES:
            raise serializers.ValidationError('The cover image must be 5 MB or smaller.')

        return value

    def create(self, validated_data):
        validated_data.pop('remove_image', None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        remove_image = validated_data.pop('remove_image', False)
        new_image = validated_data.get('cover_image')

        if remove_image and not new_image:
            validated_data['cover_image'] = None

        # Remember the old file before the save swaps it out.
        old_name = instance.cover_image.name if instance.cover_image else None
        storage = instance.cover_image.storage

        instance = super().update(instance, validated_data)

        current_name = instance.cover_image.name if instance.cover_image else None
        if old_name and old_name != current_name:
            delete_stored_file(storage, old_name)

        return instance
