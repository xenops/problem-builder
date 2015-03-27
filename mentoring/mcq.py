# -*- coding: utf-8 -*-
#
# Copyright (c) 2014-2015 Harvard, edX & OpenCraft
#
# This software's license gives you freedom; you can copy, convey,
# propagate, redistribute and/or modify this program under the terms of
# the GNU Affero General Public License (AGPL) as published by the Free
# Software Foundation (FSF), either version 3 of the License, or (at your
# option) any later version of the AGPL published by the FSF.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Affero
# General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program in a file in the toplevel directory called
# "AGPLv3".  If not, see <http://www.gnu.org/licenses/>.
#

# Imports ###########################################################

import logging

from xblock.fields import Scope, String, List
from xblock.fragment import Fragment
from xblock.validation import ValidationMessage
from xblockutils.resources import ResourceLoader

from .questionnaire import QuestionnaireAbstractBlock


# Globals ###########################################################

log = logging.getLogger(__name__)
loader = ResourceLoader(__name__)


# Make '_' a no-op so we can scrape strings
def _(text):
    return text

# Classes ###########################################################


class MCQBlock(QuestionnaireAbstractBlock):
    """
    An XBlock used to ask multiple-choice questions
    """
    student_choice = String(
        # {Last input submitted by the student
        default="",
        scope=Scope.user_state,
    )

    correct_choices = List(
        display_name=_("Correct Choice[s]"),
        help=_("Specify the value[s] that students may select for this question to be considered correct."),
        scope=Scope.content,
        list_values_provider=QuestionnaireAbstractBlock.choice_values_provider,
        list_style='set',  # Underered, unique items. Affects the UI editor.
    )
    editable_fields = QuestionnaireAbstractBlock.editable_fields + ('correct_choices', )

    def describe_choice_correctness(self, choice_value):
        if choice_value in self.correct_choices:
            if len(self.correct_choices) == 1:
                # Translators: This is an adjective, describing a choice as correct
                return self._(u"Correct")
            return self._(u"Acceptable")
        else:
            if len(self.correct_choices) == 1:
                return self._(u"Wrong")
            return self._(u"Not Acceptable")

    def submit(self, submission):
        log.debug(u'Received MCQ submission: "%s"', submission)

        correct = submission in self.correct_choices
        tips_html = []
        for tip in self.get_tips():
            if submission in tip.values:
                tips_html.append(tip.render('mentoring_view').content)

        if tips_html:
            formatted_tips = loader.render_template('templates/html/tip_choice_group.html', {
                'tips_html': tips_html,
            })

        self.student_choice = submission
        result = {
            'submission': submission,
            'status': 'correct' if correct else 'incorrect',
            'tips': formatted_tips if tips_html else None,
            'weight': self.weight,
            'score': 1 if correct else 0,
        }
        log.debug(u'MCQ submission result: %s', result)
        return result

    def author_edit_view(self, context):
        """
        The options for the 1-5 values of the Likert scale aren't child blocks but we want to
        show them in the author edit view, for clarity.
        """
        fragment = Fragment(u"<p>{}</p>".format(self.question))
        self.render_children(context, fragment, can_reorder=True, can_add=False)
        fragment.add_content(loader.render_template('templates/html/questionnaire_add_buttons.html', {}))
        fragment.add_css_url(self.runtime.local_resource_url(self, 'public/css/questionnaire-edit.css'))
        return fragment

    def validate_field_data(self, validation, data):
        """
        Validate this block's field data.
        """
        super(MCQBlock, self).validate_field_data(validation, data)

        def add_error(msg):
            validation.add(ValidationMessage(ValidationMessage.ERROR, msg))

        def choice_name(choice_value):
            for choice in self.human_readable_choices:
                if choice["value"] == choice_value:
                    return choice["display_name"]
            return choice_value

        all_values = set(self.all_choice_values)
        correct = set(data.correct_choices)

        if not all_values:
            add_error(self._(u"No choices set yet."))
        elif not correct:
            add_error(
                self._(u"You must indicate the correct answer[s], or the student will always get this question wrong.")
            )
        if len(correct) < len(data.correct_choices):
            add_error(self._(u"Duplicate correct choices set"))
        for val in (correct - all_values):
            add_error(
                self._(u"A choice value listed as correct does not exist: {choice}").format(choice=choice_name(val))
            )


class RatingBlock(MCQBlock):
    """
    An XBlock used to rate something on a five-point scale, e.g. Likert Scale
    """
    low = String(
        display_name=_("Low"),
        help=_("Label for low ratings"),
        scope=Scope.content,
        default=_("Less"),
    )
    high = String(
        display_name=_("High"),
        help=_("Label for high ratings"),
        scope=Scope.content,
        default=_("More"),
    )
    FIXED_VALUES = ["1", "2", "3", "4", "5"]
    correct_choices = List(
        display_name=_("Accepted Choice[s]"),
        help=_("Specify the rating value[s] that students may select for this question to be considered correct."),
        scope=Scope.content,
        default=FIXED_VALUES,
        list_values_provider=QuestionnaireAbstractBlock.choice_values_provider,
        list_style='set',  # Underered, unique items. Affects the UI editor.
    )
    editable_fields = MCQBlock.editable_fields + ('low', 'high')

    @property
    def all_choice_values(self):
        return self.FIXED_VALUES + [c.value for c in self.custom_choices]

    @property
    def human_readable_choices(self):
        display_names = ["1 - {}".format(self.low), "2", "3", "4", "5 - {}".format(self.high)]
        return [
            {"display_name": dn, "value": val} for val, dn in zip(self.FIXED_VALUES, display_names)
            ] + super(RatingBlock, self).human_readable_choices

    def author_edit_view(self, context):
        """
        The options for the 1-5 values of the Likert scale aren't child blocks but we want to
        show them in the author edit view, for clarity.
        """
        fragment = Fragment()
        fragment.add_content(loader.render_template('templates/html/ratingblock_edit_preview.html', {
            'question': self.question,
            'low': self.low,
            'high': self.high,
            'accepted_statuses': [None] + [self.describe_choice_correctness(c) for c in "12345"],
        }))
        self.render_children(context, fragment, can_reorder=True, can_add=False)
        fragment.add_content(loader.render_template('templates/html/questionnaire_add_buttons.html', {}))
        fragment.add_css_url(self.runtime.local_resource_url(self, 'public/css/questionnaire-edit.css'))
        return fragment
