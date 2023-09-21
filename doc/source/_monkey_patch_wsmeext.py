from sphinx.ext import autodoc
from sphinx.locale import _
from wsmeext import sphinxext
import wsme


class TypeDocumenter(autodoc.ClassDocumenter):
    objtype = 'type'
    directivetype = 'type'
    domain = 'wsme'
    required_arguments = 1
    default_samples_slot = 'after-docstring'
    option_spec = dict(
        autodoc.ClassDocumenter.option_spec,
        **{'protocols': lambda l: [v.strip() for v in l.split(',')],
           'samples-slot': sphinxext.check_samples_slot,
           })

    @staticmethod
    def can_document_member(member, membername, isattr, parent):
        # we don't want to be automaticaly used
        # TODO check if the member is registered an an exposed type
        return False

    def format_name(self):
        return self.object.__name__

    def format_signature(self):
        return u''

    def add_directive_header(self, sig):
        super(TypeDocumenter, self).add_directive_header(sig)
        # remove the :module: option that was added by ClassDocumenter
        result_len = len(self.directive.result)
        for index, item in zip(reversed(range(result_len)),
                               reversed(self.directive.result)):
            if ':module:' in item:
                self.directive.result.pop(index)

    def import_object(self):
        if super(TypeDocumenter, self).import_object():
            wsme.types.register_type(self.object)
            return True
        else:
            return False

    def add_content(self, more_content):
        # Check where to include the samples
        samples_slot = self.options.samples_slot or self.default_samples_slot

        def add_docstring():
            super(TypeDocumenter, self).add_content(more_content)

        def add_samples():
            protocols = sphinxext.get_protocols(
                self.options.protocols or self.env.app.config.wsme_protocols
            )
            content = []
            if protocols:
                sample_obj = sphinxext.make_sample_object(self.object)
                content.extend([
                    _(u'Data samples:'),
                    u'',
                    u'.. cssclass:: toggle',
                    u''
                ])
                for name, protocol in protocols:
                    language, sample = protocol.encode_sample_value(
                        self.object, sample_obj, format=True)
                    content.extend([
                        name,
                        u'    .. code-block:: ' + language,
                        u'',
                    ])
                    content.extend(
                        u' ' * 8 + line
                        for line in str(sample).split('\n'))
            for line in content:
                self.add_line(line, u'<wsmeext.sphinxext')
            self.add_line(u'', '<wsmeext.sphinxext>')
        if samples_slot == 'after-docstring':
            add_docstring()
            add_samples()
        elif samples_slot == 'before-docstring':
            add_samples()
            add_docstring()
        else:
            add_docstring()


class AttributeDocumenter(autodoc.AttributeDocumenter):
    datatype = None
    domain = 'wsme'

    @staticmethod
    def can_document_member(member, membername, isattr, parent):
        return isinstance(parent, TypeDocumenter)

    def import_object(self):
        success = super(AttributeDocumenter, self).import_object()
        if success:
            self.datatype = self.object.datatype
        return success

    def add_content(self, more_content):
        self.add_line(
            u':type: %s' % sphinxext.datatypename(self.datatype),
            '<wsmeext.sphinxext>'
        )
        self.add_line(u'', '<wsmeext.sphinxext>')
        super(AttributeDocumenter, self).add_content(more_content)

    def add_directive_header(self, sig):
        super(AttributeDocumenter, self).add_directive_header(sig)


# FIXME(stephenfin): Remove this as soon as we have a new release of wsme that
# includes the fix
# https://review.opendev.org/c/x/wsme/+/893677
sphinxext.TypeDocumenter = TypeDocumenter
sphinxext.AttributeDocumenter = AttributeDocumenter
