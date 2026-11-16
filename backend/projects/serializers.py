import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import URLValidator
from rest_framework import serializers

from .models import Project

logger = logging.getLogger(__name__)

IMAGE_MAX_BYTES = 5 * 1024 * 1024

# Only web addresses: a javascript: or data: link in an href would run when a
# visitor clicks the card.
link_validator = URLValidator(schemes=['http', 'https'])
WEB_ADDRESS_MESSAGE = 'Enter a full web address starting with http:// or https://.'


def delete_stored_file(storage, name):
    """Remove an uploaded image from storage (local disk or Cloudinary).

    Takes the storage and name rather than a FieldFile: FieldFile.delete() also
    blanks the field on the model instance, which is wrong when the instance
    has just been given a replacement. A failure here must never undo the edit
    that was just saved, so it's logged, not raised.
    """
    if not name:
        return

    try:
        storage.delete(name)
    except Exception:
        logger.warning('Could not delete project image %s', name, exc_info=True)


class ProjectAdminSerializer(serializers.ModelSerializer):
    """What the dashboard reads and writes. Staff-only (see the viewset)."""

    image_url = serializers.SerializerMethodField()
    # Ticked in the form to drop the current picture without uploading another.
    remove_image = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = Project
        fields = [
            'id',
            'title',
            'category',
            'description',
            'highlight',
            'link_url',
            'image',
            'remove_image',
            'image_url',
            'is_published',
            'show_on_home',
            'sort_order',
            'created_at',
            'updated_at',
        ]
        # Order only changes through the dashboard's reorder action.
        read_only_fields = ['id', 'sort_order', 'created_at', 'updated_at']
        extra_kwargs = {
            # Reads go through image_url (an address that works for uploads,
            # Cloudinary and the built-in site images); this field is upload-only.
            'image': {'write_only': True, 'required': False, 'allow_null': True},
            # DRF's own URL check runs first, so its message is the one shown.
            'link_url': {'error_messages': {'invalid': WEB_ADDRESS_MESSAGE}},
        }

    def get_image_url(self, obj):
        url = obj.image_src

        if not url:
            return ''

        request = self.context.get('request')

        if request and not url.startswith(('http://', 'https://')):
            return request.build_absolute_uri(url)

        return url

    def validate_title(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError('A title is required.')

        return value

    def validate_description(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError('A short description is required.')

        return value

    def validate_category(self, value):
        value = ' '.join(value.split())

        if not value:
            raise serializers.ValidationError('A category is required.')

        # "branding" and "Branding" would otherwise become two filter tabs on
        # the public page. Reuse whichever spelling is already in use.
        existing = (
            Project.objects.filter(category__iexact=value)
            .values_list('category', flat=True)
            .first()
        )

        return existing or value

    def validate_highlight(self, value):
        return value.strip()

    def validate_link_url(self, value):
        value = value.strip()

        if value:
            try:
                link_validator(value)
            except DjangoValidationError:
                raise serializers.ValidationError(WEB_ADDRESS_MESSAGE)

        return value

    def validate_image(self, value):
        # ImageField has already confirmed it's a real, decodable image
        # (which also rules out SVG, a script-carrying format).
        if value and value.size > IMAGE_MAX_BYTES:
            raise serializers.ValidationError('The image must be 5 MB or smaller.')

        return value

    def create(self, validated_data):
        validated_data.pop('remove_image', None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        remove_image = validated_data.pop('remove_image', False)
        new_image = validated_data.get('image')

        if remove_image and not new_image:
            validated_data['image'] = None

        # Remember the old upload before the save swaps it out.
        old_name = instance.image.name if instance.image else None
        storage = instance.image.storage

        if new_image or remove_image:
            # The built-in picture is only a stand-in until someone provides
            # their own, or deliberately removes it.
            instance.static_image = ''

        instance = super().update(instance, validated_data)

        current_name = instance.image.name if instance.image else None
        if old_name and old_name != current_name:
            delete_stored_file(storage, old_name)

        return instance
