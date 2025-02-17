# -*- coding: utf-8 -*-

#  Licensed under the Apache License, Version 2.0 (the "License"); you may
#  not use this file except in compliance with the License. You may obtain
#  a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License.


import datetime
import errno
import os
import sys
import logging
import tempfile
from argparse import ArgumentParser

from flask import Flask, request, abort, send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix

from linebot.v3 import (
    WebhookHandler
)
from linebot.v3.models import (
    UnknownEvent
)
from linebot.v3.exceptions import (
    InvalidSignatureError
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    LocationMessageContent,
    StickerMessageContent,
    ImageMessageContent,
    VideoMessageContent,
    AudioMessageContent,
    FileMessageContent,
    UserSource,
    RoomSource,
    GroupSource,
    FollowEvent,
    UnfollowEvent,
    JoinEvent,
    LeaveEvent,
    PostbackEvent,
    BeaconEvent,
    MemberJoinedEvent,
    MemberLeftEvent,
)
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    MessagingApiBlob,
    ReplyMessageRequest,
    PushMessageRequest,
    MulticastRequest,
    BroadcastRequest,
    TextMessage,
    ApiException,
    LocationMessage,
    StickerMessage,
    ImageMessage,
    TemplateMessage,
    FlexMessage,
    Emoji,
    QuickReply,
    QuickReplyItem,
    ConfirmTemplate,
    ButtonsTemplate,
    CarouselTemplate,
    CarouselColumn,
    ImageCarouselTemplate,
    ImageCarouselColumn,
    FlexBubble,
    FlexImage,
    FlexBox,
    FlexText,
    FlexIcon,
    FlexButton,
    FlexSeparator,
    FlexContainer,
    MessageAction,
    URIAction,
    PostbackAction,
    DatetimePickerAction,
    CameraAction,
    CameraRollAction,
    LocationAction,
    ErrorResponse
)

from linebot.v3.insight import (
    ApiClient as InsightClient,
    Insight
)


app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_host=1, x_proto=1)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
app.logger.setLevel(logging.INFO)


# get channel_secret and channel_access_token from your environment variable
channel_secret = os.getenv('LINE_CHANNEL_SECRET', None)
channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', None)
if channel_secret is None or channel_access_token is None:
    print('Specify LINE_CHANNEL_SECRET and LINE_CHANNEL_ACCESS_TOKEN as environment variables.')
    sys.exit(1)

handler = WebhookHandler(channel_secret)

static_tmp_path = os.path.join(os.path.dirname(__file__), 'static', 'tmp')

configuration = Configuration(
    access_token=channel_access_token
)


# function for create tmp dir for download content
def make_static_tmp_dir():
    try:
        os.makedirs(static_tmp_path)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(static_tmp_path):
            pass
        else:
            raise


@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except ApiException as e:
        app.logger.warn("Got exception from LINE Messaging API: %s\n" % e.body)
    except InvalidSignatureError:
        abort(400)

    return 'OK'


@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    text = event.message.text
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        if text == 'profile':
            if isinstance(event.source, UserSource):
                profile = line_bot_api.get_profile(user_id=event.source.user_id)
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[
                            TextMessage(text='Display name: ' + profile.display_name),
                            TextMessage(text='Status message: ' + str(profile.status_message))
                        ]
                    )
                )
            else:
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="Bot can't use profile API without user ID")]
                    )
                )
        elif text == 'emojis':
            emojis = [Emoji(index=0, product_id="5ac1bfd5040ab15980c9b435", emoji_id="001"),
                      Emoji(index=13, product_id="5ac1bfd5040ab15980c9b435", emoji_id="002")]
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text='$ LINE emoji $', emojis=emojis)]
                )
            )
        elif text == 'quota':
            quota = line_bot_api.get_message_quota()
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        TextMessage(text='type: ' + quota.type),
                        TextMessage(text='value: ' + str(quota.value))
                    ]
                )
            )
        elif text == 'quota_consumption':
            quota_consumption = line_bot_api.get_message_quota_consumption()
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        TextMessage(text='total usage: ' + str(quota_consumption.total_usage))
                    ]
                )
            )
        elif text == 'push':
            line_bot_api.push_message(
                PushMessageRequest(
                    to=event.source.user_id,
                    messages=[TextMessage(text='PUSH!')]
                )
            )
        elif text == 'multicast':
            line_bot_api.multicast(
                MulticastRequest(
                    to=[event.source.user_id],
                    messages=[TextMessage(text="THIS IS A MULTICAST MESSAGE, but it's slower than PUSH.")]
                )
            )
        elif text == 'broadcast':
            line_bot_api.broadcast(
                BroadcastRequest(
                    messages=[TextMessage(text='THIS IS A BROADCAST MESSAGE')]
                )
            )
        elif text.startswith('broadcast '):  # broadcast 20190505
            date = text.split(' ')[1]
            app.logger.info("Getting broadcast result: " + date)
            result = line_bot_api.get_number_of_sent_broadcast_messages(var_date=date)
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        TextMessage(text='Number of sent broadcast messages: ' + date),
                        TextMessage(text='status: ' + str(result.status)),
                        TextMessage(text='success: ' + str(result.success)),
                    ]
                )
            )
        elif text == 'bye':
            if isinstance(event.source, GroupSource):
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="Leaving group")]
                    )
                )
                line_bot_api.leave_group(event.source.group_id)
            elif isinstance(event.source, RoomSource):
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="Leaving room")]
                    )
                )
                line_bot_api.leave_room(room_id=event.source.room_id)
            else:
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[
                            TextMessage(text="Bot can't leave from 1:1 chat")
                        ]
                    )
                )
        elif text == 'image':
            url = request.url_root + '/static/logo.png'
            url = url.replace("http", "https")
            app.logger.info("url=" + url)
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        ImageMessage(original_content_url=url, preview_image_url=url)
                    ]
                )
            )
        elif text == 'confirm':
            confirm_template = ConfirmTemplate(
                text='Do it?',
                actions=[
                    MessageAction(label='Yes', text='Yes!'),
                    MessageAction(label='No', text='No!')
                ]
            )
            template_message = TemplateMessage(
                alt_text='Confirm alt text',
                template=confirm_template
            )
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[template_message]
                )
            )
        elif text == 'buttons':
            buttons_template = ButtonsTemplate(
                title='My buttons sample',
                text='Hello, my buttons',
                actions=[
                    URIAction(label='Go to line.me', uri='https://line.me'),
                    PostbackAction(label='ping', data='ping'),
                    PostbackAction(label='ping with text', data='ping', text='ping'),
                    MessageAction(label='Translate Rice', text='米')
                ])
            template_message = TemplateMessage(
                alt_text='Buttons alt text',
                template=buttons_template
            )
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[template_message]
                )
            )
        elif text == 'carousel':
            carousel_template = CarouselTemplate(
                columns=[
                    CarouselColumn(
                        text='hoge1',
                        title='fuga1',
                        actions=[
                            URIAction(label='Go to line.me', uri='https://line.me'),
                            PostbackAction(label='ping', data='ping')
                        ]
                    ),
                    CarouselColumn(
                        text='hoge2',
                        title='fuga2',
                        actions=[
                            PostbackAction(label='ping with text', data='ping', text='ping'),
                            MessageAction(label='Translate Rice', text='米')
                        ]
                    )
                ]
            )
            template_message = TemplateMessage(
                alt_text='Carousel alt text', template=carousel_template)
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[template_message]
                )
            )
        elif text == 'image_carousel':
            image_carousel_template = ImageCarouselTemplate(columns=[
                ImageCarouselColumn(image_url='https://via.placeholder.com/1024x1024',
                                    action=DatetimePickerAction(label='datetime',
                                                                data='datetime_postback',
                                                                mode='datetime')),
                ImageCarouselColumn(image_url='https://via.placeholder.com/1024x1024',
                                    action=DatetimePickerAction(label='date',
                                                                data='date_postback',
                                                                mode='date'))
            ])
            template_message = TemplateMessage(
                alt_text='ImageCarousel alt text', template=image_carousel_template)
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[template_message]
                )
            )
        elif text == 'imagemap':
            pass
        elif text == 'flex':
            bubble = FlexBubble(
                direction='ltr',
                hero=FlexImage(
                    url='https://example.com/cafe.jpg',
                    size='full',
                    aspect_ratio='20:13',
                    aspect_mode='cover',
                    action=URIAction(uri='http://example.com', label='label')
                ),
                body=FlexBox(
                    layout='vertical',
                    contents=[
                        # title
                        FlexText(text='Brown Cafe', weight='bold', size='xl'),
                        # review
                        FlexBox(
                            layout='baseline',
                            margin='md',
                            contents=[
                                FlexIcon(size='sm', url='https://example.com/gold_star.png'),
                                FlexIcon(size='sm', url='https://example.com/grey_star.png'),
                                FlexIcon(size='sm', url='https://example.com/gold_star.png'),
                                FlexIcon(size='sm', url='https://example.com/gold_star.png'),
                                FlexIcon(size='sm', url='https://example.com/grey_star.png'),
                                FlexText(text='4.0', size='sm', color='#999999', margin='md', flex=0)
                            ]
                        ),
                        # info
                        FlexBox(
                            layout='vertical',
                            margin='lg',
                            spacing='sm',
                            contents=[
                                FlexBox(
                                    layout='baseline',
                                    spacing='sm',
                                    contents=[
                                        FlexText(
                                            text='Place',
                                            color='#aaaaaa',
                                            size='sm',
                                            flex=1
                                        ),
                                        FlexText(
                                            text='Shinjuku, Tokyo',
                                            wrap=True,
                                            color='#666666',
                                            size='sm',
                                            flex=5
                                        )
                                    ],
                                ),
                                FlexBox(
                                    layout='baseline',
                                    spacing='sm',
                                    contents=[
                                        FlexText(
                                            text='Time',
                                            color='#aaaaaa',
                                            size='sm',
                                            flex=1
                                        ),
                                        FlexText(
                                            text="10:00 - 23:00",
                                            wrap=True,
                                            color='#666666',
                                            size='sm',
                                            flex=5,
                                        ),
                                    ],
                                ),
                            ],
                        )
                    ],
                ),
                footer=FlexBox(
                    layout='vertical',
                    spacing='sm',
                    contents=[
                        # callAction
                        FlexButton(
                            style='link',
                            height='sm',
                            action=URIAction(label='CALL', uri='tel:000000'),
                        ),
                        # separator
                        FlexSeparator(),
                        # websiteAction
                        FlexButton(
                            style='link',
                            height='sm',
                            action=URIAction(label='WEBSITE', uri="https://example.com")
                        )
                    ]
                ),
            )
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[FlexMessage(alt_text="hello", contents=bubble)]
                )
            )
        elif text == 'flex_update_1':
            bubble_string = """
            {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                {
                    "type": "image",
                    "url": "https://scdn.line-apps.com/n/channel_devcenter/img/flexsnapshot/clip/clip3.jpg",
                    "position": "relative",
                    "size": "full",
                    "aspectMode": "cover",
                    "aspectRatio": "1:1",
                    "gravity": "center"
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                    {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                        {
                            "type": "text",
                            "text": "Brown Hotel",
                            "weight": "bold",
                            "size": "xl",
                            "color": "#ffffff"
                        },
                        {
                            "type": "box",
                            "layout": "baseline",
                            "margin": "md",
                            "contents": [
                            {
                                "type": "icon",
                                "size": "sm",
                                "url": "https://scdn.line-apps.com/n/channel_devcenter/img/fx/review_gold_star_28.png"
                            },
                            {
                                "type": "icon",
                                "size": "sm",
                                "url": "https://scdn.line-apps.com/n/channel_devcenter/img/fx/review_gold_star_28.png"
                            },
                            {
                                "type": "icon",
                                "size": "sm",
                                "url": "https://scdn.line-apps.com/n/channel_devcenter/img/fx/review_gold_star_28.png"
                            },
                            {
                                "type": "icon",
                                "size": "sm",
                                "url": "https://scdn.line-apps.com/n/channel_devcenter/img/fx/review_gold_star_28.png"
                            },
                            {
                                "type": "icon",
                                "size": "sm",
                                "url": "https://scdn.line-apps.com/n/channel_devcenter/img/fx/review_gray_star_28.png"
                            },
                            {
                                "type": "text",
                                "text": "4.0",
                                "size": "sm",
                                "color": "#d6d6d6",
                                "margin": "md",
                                "flex": 0
                            }
                            ]
                        }
                        ]
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                        {
                            "type": "text",
                            "text": "¥62,000",
                            "color": "#a9a9a9",
                            "decoration": "line-through",
                            "align": "end"
                        },
                        {
                            "type": "text",
                            "text": "¥42,000",
                            "color": "#ebebeb",
                            "size": "xl",
                            "align": "end"
                        }
                        ]
                    }
                    ],
                    "position": "absolute",
                    "offsetBottom": "0px",
                    "offsetStart": "0px",
                    "offsetEnd": "0px",
                    "backgroundColor": "#00000099",
                    "paddingAll": "20px"
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                    {
                        "type": "text",
                        "text": "SALE",
                        "color": "#ffffff"
                    }
                    ],
                    "position": "absolute",
                    "backgroundColor": "#ff2600",
                    "cornerRadius": "20px",
                    "paddingAll": "5px",
                    "offsetTop": "10px",
                    "offsetEnd": "10px",
                    "paddingStart": "10px",
                    "paddingEnd": "10px"
                }
                ],
                "paddingAll": "0px"
            }
            }
            """
            message = FlexMessage(alt_text="hello", contents=FlexContainer.from_json(bubble_string))
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[message]
                )
            )
        elif text == 'quick_reply':
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(
                        text='Quick reply',
                        quick_reply=QuickReply(
                            items=[
                                QuickReplyItem(
                                    action=PostbackAction(label="label1", data="data1")
                                ),
                                QuickReplyItem(
                                    action=MessageAction(label="label2", text="text2")
                                ),
                                QuickReplyItem(
                                    action=DatetimePickerAction(label="label3",
                                                                data="data3",
                                                                mode="date")
                                ),
                                QuickReplyItem(
                                    action=CameraAction(label="label4")
                                ),
                                QuickReplyItem(
                                    action=CameraRollAction(label="label5")
                                ),
                                QuickReplyItem(
                                    action=LocationAction(label="label6")
                                ),
                            ]
                        )
                    )]
                )
            )
        elif text == 'link_token' and isinstance(event.source, UserSource):
            link_token_response = line_bot_api.issue_link_token(user_id=event.source.user_id)
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text='link_token: ' + link_token_response.link_token)]
                )
            )
        elif text == 'insight_message_delivery':
            with InsightClient(configuration) as api_client:
                line_bot_insight_api = Insight(api_client)
                today = datetime.date.today().strftime("%Y%m%d")
                response = line_bot_insight_api.get_number_of_message_deliveries(var_date=today)
                if response.status == 'ready':
                    messages = [
                        TextMessage(text='broadcast: ' + str(response.broadcast)),
                        TextMessage(text='targeting: ' + str(response.targeting)),
                    ]
                else:
                    messages = [TextMessage(text='status: ' + response.status)]
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=messages
                )
            )
        elif text == 'insight_followers':
            with InsightClient(configuration) as api_client:
                line_bot_insight_api = Insight(api_client)
                today = datetime.date.today().strftime("%Y%m%d")
                response = line_bot_insight_api.get_number_of_followers(var_date=today)
            if response.status == 'ready':
                messages = [
                    TextMessage(text='followers: ' + str(response.followers)),
                    TextMessage(text='targetedReaches: ' + str(response.targeted_reaches)),
                    TextMessage(text='blocks: ' + str(response.blocks)),
                ]
            else:
                messages = [TextMessage(text='status: ' + response.status)]
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=messages
                )
            )
        elif text == 'insight_demographic':
            with InsightClient(configuration) as api_client:
                line_bot_insight_api = Insight(api_client)
                response = line_bot_insight_api.get_friends_demographics()
            if response.available:
                messages = ["{gender}: {percentage}".format(gender=it.gender, percentage=it.percentage)
                            for it in response.genders]
            else:
                messages = [TextMessage(text='available: false')]
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=messages
                )
            )
        elif text == 'with http info':
            response = line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text='see application log')]
                )
            )
            app.logger.info("Got response with http status code: " + str(response.status_code))
            app.logger.info("Got x-line-request-id: " + response.headers['x-line-request-id'])
            app.logger.info("Got response with http body: " + str(response.data))
        elif text == 'with http info error':
            try:
                line_bot_api.reply_message_with_http_info(
                    ReplyMessageRequest(
                        reply_token='invalid-reply-token',
                        messages=[TextMessage(text='see application log')]
                    )
                )
            except ApiException as e:
                app.logger.info("Got response with http status code: " + str(e.status))
                app.logger.info("Got x-line-request-id: " + e.headers['x-line-request-id'])
                app.logger.info("Got response with http body: " + str(ErrorResponse.from_json(e.body)))
        else:
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=event.message.text)]
                )
            )


@handler.add(MessageEvent, message=LocationMessageContent)
def handle_location_message(event):
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[LocationMessage(
                    title='Location',
                    address=event.message.address,
                    latitude=event.message.latitude,
                    longitude=event.message.longitude
                )]
            )
        )


@handler.add(MessageEvent, message=StickerMessageContent)
def handle_sticker_message(event):
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[StickerMessage(
                    package_id=event.message.package_id,
                    sticker_id=event.message.sticker_id)
                ]
            )
        )


# Other Message Type
@handler.add(MessageEvent, message=(ImageMessageContent,
                                    VideoMessageContent,
                                    AudioMessageContent))
def handle_content_message(event):
    if isinstance(event.message, ImageMessageContent):
        ext = 'jpg'
    elif isinstance(event.message, VideoMessageContent):
        ext = 'mp4'
    elif isinstance(event.message, AudioMessageContent):
        ext = 'm4a'
    else:
        return

    with ApiClient(configuration) as api_client:
        line_bot_blob_api = MessagingApiBlob(api_client)
        message_content = line_bot_blob_api.get_message_content(message_id=event.message.id)
        with tempfile.NamedTemporaryFile(dir=static_tmp_path, prefix=ext + '-', delete=False) as tf:
            tf.write(message_content)
            tempfile_path = tf.name

    dist_path = tempfile_path + '.' + ext
    dist_name = os.path.basename(dist_path)
    os.rename(tempfile_path, dist_path)

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[
                    TextMessage(text='Save content.'),
                    TextMessage(text=request.host_url + os.path.join('static', 'tmp', dist_name))
                ]
            )
        )


@handler.add(MessageEvent, message=FileMessageContent)
def handle_file_message(event):
    with ApiClient(configuration) as api_client:
        line_bot_blob_api = MessagingApiBlob(api_client)
        message_content = line_bot_blob_api.get_message_content(message_id=event.message.id)
        with tempfile.NamedTemporaryFile(dir=static_tmp_path, prefix='file-', delete=False) as tf:
            tf.write(message_content)
            tempfile_path = tf.name

    dist_path = tempfile_path + '-' + event.message.file_name
    dist_name = os.path.basename(dist_path)
    os.rename(tempfile_path, dist_path)

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[
                    TextMessage(text='Save file.'),
                    TextMessage(text=request.host_url + os.path.join('static', 'tmp', dist_name))
                ]
            )
        )


@handler.add(FollowEvent)
def handle_follow(event):
    app.logger.info("Got Follow event:" + event.source.user_id)
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text='Got follow event')]
            )
        )


@handler.add(UnfollowEvent)
def handle_unfollow(event):
    app.logger.info("Got Unfollow event:" + event.source.user_id)


@handler.add(JoinEvent)
def handle_join(event):
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text='Joined this ' + event.source.type)]
            )
        )


@handler.add(LeaveEvent)
def handle_leave():
    app.logger.info("Got leave event")


@handler.add(PostbackEvent)
def handle_postback(event: PostbackEvent):
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        if event.postback.data == 'ping':
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text='pong')]
                )
            )
        elif event.postback.data == 'datetime_postback':
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=event.postback.params['datetime'])]
                )
            )
        elif event.postback.data == 'date_postback':
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=event.postback.params['date'])]
                )
            )


@handler.add(BeaconEvent)
def handle_beacon(event: BeaconEvent):
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text='Got beacon event. hwid={}, device_message(hex string)={}'.format(
                    event.beacon.hwid, event.beacon.dm))]
            )
        )


@handler.add(MemberJoinedEvent)
def handle_member_joined(event):
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text='Got memberJoined event. event={}'.format(event))]
            )
        )


@handler.add(MemberLeftEvent)
def handle_member_left(event):
    app.logger.info("Got memberLeft event")


@handler.add(UnknownEvent)
def handle_unknown_left(event):
    app.logger.info(f"unknown event {event}")


@app.route('/static/<path:path>')
def send_static_content(path):
    return send_from_directory('static', path)


if __name__ == "__main__":
    arg_parser = ArgumentParser(
        usage='Usage: python ' + __file__ + ' [--port <port>] [--help]'
    )
    arg_parser.add_argument('-p', '--port', type=int, default=8000, help='port')
    arg_parser.add_argument('-d', '--debug', default=False, help='debug')
    options = arg_parser.parse_args()

    # create tmp dir for download content
    make_static_tmp_dir()

    app.run(debug=options.debug, port=options.port)