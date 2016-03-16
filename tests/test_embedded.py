import pytest

from django.test import TestCase
from mongoengine import Document, EmbeddedDocument, fields
from rest_framework.compat import unicode_repr

from rest_framework.serializers import Serializer
from rest_framework import fields as drf_fields
from rest_framework_mongoengine.fields import DocumentField, GenericEmbeddedField
from rest_framework_mongoengine.serializers import (DocumentSerializer,
                                                    EmbeddedDocumentSerializer)

from .utils import dedent, FieldValues
from .models import DumbEmbedded, OtherEmbedded


class TestGenericEmbeddedField(FieldValues, TestCase):
    field = GenericEmbeddedField()

    valid_inputs = [
        ({'_cls': 'DumbEmbedded', 'name': "Name"}, DumbEmbedded(name="Name")),
    ]

    invalid_inputs = [
        ({'_cls': 'InvalidModel', 'name': "Name"}, "Document `InvalidModel` has not been defined."),
    ]

    outputs = [
        (DumbEmbedded(name="Name"), {'_cls': 'DumbEmbedded', 'name': "Name", 'foo': None}),
    ]


class NestedEmbeddedDoc(EmbeddedDocument):
    name = fields.StringField()
    embedded = fields.EmbeddedDocumentField(DumbEmbedded)


class SelfEmbeddingDoc(EmbeddedDocument):
    name = fields.StringField()
    embedded = fields.EmbeddedDocumentField('self')


class EmbeddingDoc(Document):
    embedded = fields.EmbeddedDocumentField(DumbEmbedded)


class RequiredEmbeddingDoc(Document):
    embedded = fields.EmbeddedDocumentField(DumbEmbedded, required=True)


class ListEmbeddingDoc(Document):
    embedded_list = fields.EmbeddedDocumentListField(DumbEmbedded)


class NestedEmbeddingDoc(Document):
    embedded = fields.EmbeddedDocumentField(NestedEmbeddedDoc)


class RecursiveEmbeddingDoc(Document):
    embedded = fields.EmbeddedDocumentField(SelfEmbeddingDoc)


class GenericEmbeddingModel(Document):
    embedded = fields.GenericEmbeddedDocumentField()


class TestEmbeddedMapping(TestCase):
    def test_embbedded(self):
        class TestSerializer(EmbeddedDocumentSerializer):
            class Meta:
                model = DumbEmbedded
        expected = dedent("""
            TestSerializer():
                name = CharField(required=False)
                foo = IntegerField(required=False)
        """)
        assert unicode_repr(TestSerializer()) == expected

    def test_embedding(self):
        class TestSerializer(DocumentSerializer):
            class Meta:
                model = EmbeddingDoc
                depth = 1
        expected = dedent("""
            TestSerializer():
                id = ObjectIdField(read_only=True)
                embedded = NestedSerializer(required=False):
                    name = CharField(required=False)
                    foo = IntegerField(required=False)
        """)
        assert unicode_repr(TestSerializer()) == expected

    def test_embedding_nodepth(self):
        # FIXME: should be the same
        class TestSerializer(DocumentSerializer):
            class Meta:
                model = EmbeddingDoc
                depth = 0
        expected = dedent("""
            TestSerializer():
                id = ObjectIdField(read_only=True)
                embedded = HiddenField(default=None)
        """)
        assert unicode_repr(TestSerializer()) == expected

    def test_embedding_list(self):
        class TestSerializer(DocumentSerializer):
            class Meta:
                model = ListEmbeddingDoc
                depth = 1
        expected = dedent("""
            TestSerializer():
                id = ObjectIdField(read_only=True)
                embedded_list = NestedSerializer(many=True, required=False):
                    name = CharField(required=False)
                    foo = IntegerField(required=False)
        """)
        assert unicode_repr(TestSerializer()) == expected

    def test_embedding_required(self):
        class TestSerializer(DocumentSerializer):
            class Meta:
                model = RequiredEmbeddingDoc
                depth = 1
        expected = dedent("""
            TestSerializer():
                id = ObjectIdField(read_only=True)
                embedded = NestedSerializer(required=True):
                    name = CharField(required=False)
                    foo = IntegerField(required=False)
        """)
        assert unicode_repr(TestSerializer()) == expected

    def test_embedding_nested(self):
        class TestSerializer(DocumentSerializer):
            class Meta:
                model = NestedEmbeddingDoc
                depth = 10
        expected = dedent("""
            TestSerializer():
                id = ObjectIdField(read_only=True)
                embedded = NestedSerializer(required=False):
                    name = CharField(required=False)
                    embedded = NestedSerializer(required=False):
                        name = CharField(required=False)
                        foo = IntegerField(required=False)
        """)
        assert unicode_repr(TestSerializer()) == expected

    def test_embedding_recursive(self):
        # FIXME: should be something
        class TestSerializer(DocumentSerializer):
            class Meta:
                model = RecursiveEmbeddingDoc
                depth = 3
        expected = dedent("""
            TestSerializer():
                id = ObjectIdField(read_only=True)
                embedded = NestedSerializer(required=False):
                    name = CharField(required=False)
                    embedded = NestedSerializer(required=False):
                        name = CharField(required=False)
                        embedded = NestedSerializer(required=False):
                            name = CharField(required=False)
                            embedded = HiddenField(default=None)
        """)
        assert unicode_repr(TestSerializer()) == expected

    def test_embedding_custom_field(self):

        class CustomEmbedding(DocumentField):
            pass

        class TestSerializer(DocumentSerializer):
            serializer_embedded_field = CustomEmbedding

            class Meta:
                model = EmbeddingDoc
                depth = 1

        expected = dedent("""
            TestSerializer():
                id = ObjectIdField(read_only=True)
                embedded = CustomEmbedding(model_field=<mongoengine.fields.EmbeddedDocumentField: embedded>, required=False)
        """)
        assert unicode_repr(TestSerializer()) == expected

    def test_embedding_custom_generic(self):

        class CustomEmbedding(DocumentField):
            pass

        class TestSerializer(DocumentSerializer):
            serializer_embedded_generic = CustomEmbedding

            class Meta:
                model = GenericEmbeddingModel
                depth = 1

        expected = dedent("""
            TestSerializer():
                id = ObjectIdField(read_only=True)
                embedded = CustomEmbedding(model_field=<mongoengine.fields.GenericEmbeddedDocumentField: embedded>, required=False)
        """)
        assert unicode_repr(TestSerializer()) == expected

    def test_embedding_custom_nested(self):
        class CustomEmbeddingSerializer(Serializer):
            ref = drf_fields.CharField()

        class TestSerializer(DocumentSerializer):
            serializer_embedded_nested = CustomEmbeddingSerializer

            class Meta:
                model = EmbeddingDoc
                depth = 1

        expected = dedent("""
            TestSerializer():
                id = ObjectIdField(read_only=True)
                embedded = NestedSerializer(required=False):
                    ref = CharField()
        """)
        assert unicode_repr(TestSerializer()) == expected


class TestEmbeddedIntegration(TestCase):
    def tearDown(self):
        EmbeddingDoc.drop_collection()

    def test_retrival(self):
        instance = EmbeddingDoc.objects.create(
            embedded=DumbEmbedded(name="Foo")
        )

        class TestSerializer(DocumentSerializer):
            class Meta:
                model = EmbeddingDoc
                depth = 1

        serializer = TestSerializer(instance)
        expected = {
            'id': str(instance.id),
            'embedded': {'name': "Foo", 'foo': None},
        }
        assert serializer.data == expected

    def test_gen_retrival(self):
        instance = GenericEmbeddingModel.objects.create(
            embedded=OtherEmbedded(name="Dumb2")
        )

        class TestSerializer(DocumentSerializer):
            class Meta:
                model = GenericEmbeddingModel
                depth = 1

        serializer = TestSerializer(instance)
        expected = {
            'id': str(instance.id),
            'embedded': {'_cls': 'OtherEmbedded', 'name': "Dumb2", 'bar': None}
        }

        assert serializer.data == expected

    def test_create(self):
        class TestSerializer(DocumentSerializer):
            class Meta:
                model = EmbeddingDoc
                depth = 1

        data = {
            'embedded': {'name': "Dumb"}
        }

        # Serializer should validate okay.
        serializer = TestSerializer(data=data)
        assert serializer.is_valid()

        # Creating the instance, relationship attributes should be set.
        instance = serializer.save()
        assert instance.embedded.name == "Dumb"

        # Representation should be correct.
        expected = {
            'id': str(instance.id),
            'embedded': {'name': "Dumb", 'foo': None}
        }
        assert serializer.data == expected

    def test_gen_create(self):
        class TestSerializer(DocumentSerializer):
            class Meta:
                model = GenericEmbeddingModel
                depth = 1

        data = {
            'embedded': {'_cls': 'DumbEmbedded', 'name': "Dumb"}
        }

        serializer = TestSerializer(data=data)
        assert serializer.is_valid()

        instance = serializer.save()
        self.assertIsInstance(instance.embedded, DumbEmbedded)
        assert instance.embedded.name == "Dumb"

        expected = {
            'id': str(instance.id),
            'embedded': {'_cls': 'DumbEmbedded', 'name': "Dumb", 'foo': None}
        }
        assert serializer.data == expected

    def test_update(self):
        " whole embedded is overwritten "
        instance = EmbeddingDoc.objects.create(
            embedded=DumbEmbedded(name="Dumb", foo=123)
        )

        class TestSerializer(DocumentSerializer):
            class Meta:
                model = EmbeddingDoc
                depth = 1

        data = {
            'embedded': {'foo': 321}
        }
        serializer = TestSerializer(instance, data=data)

        assert serializer.is_valid()

        instance = serializer.save()
        assert instance.embedded.name is None
        assert instance.embedded.foo == 321

        expected = {
            'id': str(instance.id),
            'embedded': {'name': None, 'foo': 321}
        }
        assert serializer.data == expected

    def test_gen_update(self):
        instance = GenericEmbeddingModel.objects.create(
            embedded=OtherEmbedded(name="Dumb", bar=123)
        )

        class TestSerializer(DocumentSerializer):
            class Meta:
                model = GenericEmbeddingModel
                depth = 1

        data = {
            'embedded': {'_cls': 'OtherEmbedded', 'bar': 321}
        }
        serializer = TestSerializer(instance, data=data)
        self.assertTrue(serializer.is_valid())

        instance = serializer.save()
        assert instance.embedded.name is None
        assert instance.embedded.bar == 321

        expected = {
            'id': str(instance.id),
            'embedded': {'_cls': 'OtherEmbedded', 'name': None, 'bar': 321}
        }
        assert serializer.data == expected


class ValidatingEmbeddedModel(EmbeddedDocument):
    text = fields.StringField(min_length=3)


class ValidatingEmbeddingModel(Document):
    embedded = fields.EmbeddedDocumentField(ValidatingEmbeddedModel)


class ValidatingSerializer(DocumentSerializer):
    class Meta:
        model = ValidatingEmbeddingModel
        depth = 1


class ValidatingListEmbeddingModel(Document):
    embedded_list = fields.EmbeddedDocumentListField(ValidatingEmbeddedModel)


class ValidatingListSerializer(DocumentSerializer):
    class Meta:
        model = ValidatingListEmbeddingModel
        depth = 1


class TestEmbeddedValidation(TestCase):
    def test_validation_failing(self):
        serializer = ValidatingSerializer(data={'embedded': {'text': 'Fo'}})
        self.assertFalse(serializer.is_valid())
        self.assertIn('embedded', serializer.errors)
        self.assertIn('text', serializer.errors['embedded'])

    def test_validation_passing(self):
        serializer = ValidatingSerializer(data={'embedded': {'text': 'Text'}})
        self.assertTrue(serializer.is_valid())

    def test_nested_validation_failing(self):
        serializer = ValidatingListSerializer(data={'embedded_list': [{'text': 'Fo'}]})
        self.assertFalse(serializer.is_valid())
        self.assertIn('embedded_list', serializer.errors)
        self.assertIn('text', serializer.errors['embedded_list'])

    def test_nested_validation_passing(self):
        serializer = ValidatingListSerializer(data={'embedded_list': [{'text': 'Text'}]})
        self.assertTrue(serializer.is_valid())