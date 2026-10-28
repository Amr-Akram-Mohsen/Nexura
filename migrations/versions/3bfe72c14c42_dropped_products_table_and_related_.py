"""dropped products table and related tables

Revision ID: 3bfe72c14c42
Revises: 0004_email_verify_token
Create Date: 2026-09-10 23:30:50.050541

"""
from __future__ import annotations
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '3bfe72c14c42'
down_revision: Union[str, None] = '0004_email_verify_token'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # ### Drop ONLY product and store related tables safely (keeping posts, last_api_fetch, api_usage, etc.) ###
    
    # Drop content_products relation
    op.drop_index(op.f('ix_content_products_content'), table_name='content_products', if_exists=True)
    op.drop_index(op.f('ix_content_products_product'), table_name='content_products', if_exists=True)
    op.drop_table('content_products', if_exists=True)

    # Drop product_clicks
    op.drop_index(op.f('ix_product_click_link'), table_name='product_clicks', if_exists=True)
    op.drop_index(op.f('ix_product_click_user'), table_name='product_clicks', if_exists=True)
    op.drop_index(op.f('ix_product_clicks_created_at'), table_name='product_clicks', if_exists=True)
    op.drop_table('product_clicks', if_exists=True)

    # Drop product_store_links
    op.drop_index(op.f('ix_product_store_external'), table_name='product_store_links', if_exists=True)
    op.drop_index(op.f('ix_product_store_links_availability'), table_name='product_store_links', if_exists=True)
    op.drop_index(op.f('ix_product_store_links_program_name'), table_name='product_store_links', if_exists=True)
    op.drop_index(op.f('ix_product_store_price'), table_name='product_store_links', if_exists=True)
    op.drop_index(op.f('ix_product_store_program'), table_name='product_store_links', if_exists=True)
    op.drop_index(op.f('ix_product_store_store'), table_name='product_store_links', if_exists=True)
    op.drop_index(op.f('ix_product_store_variant'), table_name='product_store_links', if_exists=True)
    op.drop_table('product_store_links', if_exists=True)

    # Drop product_discovery_queue
    op.drop_index(op.f('ix_discovery_queue_discovered'), table_name='product_discovery_queue', if_exists=True)
    op.drop_index(op.f('ix_discovery_queue_status'), table_name='product_discovery_queue', if_exists=True)
    op.drop_index(op.f('ix_discovery_queue_store_status'), table_name='product_discovery_queue', if_exists=True)
    op.drop_table('product_discovery_queue', if_exists=True)

    # Drop stores table
    op.drop_index(op.f('ix_stores_network_slug'), table_name='stores', if_exists=True)
    op.drop_table('stores', if_exists=True)

    # --- Foreign Key and Column Adjustments for Existing Tables ---
    op.drop_constraint(op.f('article_authors_author_id_fkey'), 'article_authors', type_='foreignkey')
    op.drop_constraint(op.f('article_authors_article_id_fkey'), 'article_authors', type_='foreignkey')
    op.create_foreign_key(None, 'article_authors', 'articles', ['article_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key(None, 'article_authors', 'authors', ['author_id'], ['id'], ondelete='CASCADE')

    # Backfill weight in article_categories if null
    op.execute(sa.text("""
        UPDATE article_categories
        SET weight = 0
        WHERE weight IS NULL
    """))

    op.alter_column('article_categories', 'weight',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=False)
    op.drop_constraint(op.f('article_categories_category_id_fkey'), 'article_categories', type_='foreignkey')
    op.drop_constraint(op.f('article_categories_article_id_fkey'), 'article_categories', type_='foreignkey')
    op.create_foreign_key(None, 'article_categories', 'articles', ['article_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key(None, 'article_categories', 'categories', ['category_id'], ['id'], ondelete='CASCADE')
    
    op.alter_column('article_sources', 'published_at',
               existing_type=postgresql.TIMESTAMP(),
               type_=postgresql.TIMESTAMP(timezone=True),
               existing_nullable=True)
    op.drop_constraint(op.f('article_sources_article_id_fkey'), 'article_sources', type_='foreignkey')
    op.drop_constraint(op.f('article_sources_source_id_fkey'), 'article_sources', type_='foreignkey')
    op.create_foreign_key(None, 'article_sources', 'sources', ['source_id'], ['id'], ondelete='RESTRICT')
    op.create_foreign_key(None, 'article_sources', 'articles', ['article_id'], ['id'], ondelete='CASCADE')
    
    op.alter_column('articles', 'quality_score',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=False)
    
    # Backfill NULL values in enrichment_priority before enforcing NOT NULL
    op.execute(sa.text("""
        UPDATE articles
        SET enrichment_priority = 0.0
        WHERE enrichment_priority IS NULL
    """))               
    op.alter_column('articles', 'enrichment_priority',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=False,
               comment=None,
               existing_comment='Priority score for enrichment worker. Calculated before enrichment.')
    op.alter_column('articles', 'extended_metadata',
               existing_type=postgresql.JSON(astext_type=sa.Text()),
               comment=None,
               existing_comment='Raw provider-specific payload for debugging/auditing only. Do NOT use for routing or queries. Structured data (entities, categories, events) belongs in proper relational tables.',
               existing_nullable=True)
    op.alter_column('articles', 'status',
               existing_type=sa.VARCHAR(length=20),
               nullable=False)
    op.alter_column('articles', 'last_enrichment_attempt',
               existing_type=postgresql.TIMESTAMP(),
               type_=postgresql.TIMESTAMP(timezone=True),
               existing_nullable=True)
    op.drop_constraint(op.f('fk_articles_event_id'), 'articles', type_='foreignkey')
    op.drop_constraint(op.f('fk_articles_primary_source_id'), 'articles', type_='foreignkey')
    op.create_foreign_key(None, 'articles', 'events', ['event_id'], ['id'], ondelete='SET NULL')
    
    op.alter_column('authors', 'slug',
               existing_type=sa.VARCHAR(length=255),
               nullable=False)
    op.alter_column('authors', 'is_agency',
               existing_type=sa.BOOLEAN(),
               nullable=False)
    op.drop_index(op.f('ix_authors_slug'), table_name='authors', if_exists=True)
    op.create_index('ix_authors_slug', 'authors', ['slug'], unique=False)
    op.create_unique_constraint(None, 'authors', ['slug'])
    
    op.alter_column('categories', 'is_active',
               existing_type=sa.BOOLEAN(),
               nullable=False)
    op.alter_column('categories', 'sort_order',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.alter_column('categories', 'is_leaf',
               existing_type=sa.BOOLEAN(),
               nullable=False)
    op.drop_index(op.f('ix_categories_external_uri'), table_name='categories', if_exists=True)
    op.create_index('ix_categories_external_uri', 'categories', ['external_uri'], unique=False)
    op.drop_index(op.f('ix_categories_slug'), table_name='categories', if_exists=True)
    op.create_index('ix_categories_slug', 'categories', ['slug'], unique=False)
    op.create_unique_constraint(None, 'categories', ['external_uri'])
    op.create_unique_constraint(None, 'categories', ['slug'])
    
    op.alter_column('comments', 'created_at',
               existing_type=postgresql.TIMESTAMP(),
               type_=postgresql.TIMESTAMP(timezone=True),
               existing_nullable=True)
    op.alter_column('contact_messages', 'created_at',
               existing_type=postgresql.TIMESTAMP(),
               type_=postgresql.TIMESTAMP(timezone=True),
               existing_nullable=True)
    
    op.drop_index(op.f('ix_content_entities_origin'), table_name='content_entities', if_exists=True)
    op.drop_constraint(op.f('content_entities_content_id_fkey'), 'content_entities', type_='foreignkey')
    op.drop_constraint(op.f('content_entities_entity_id_fkey'), 'content_entities', type_='foreignkey')
    op.create_foreign_key(None, 'content_entities', 'entities', ['entity_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key(None, 'content_entities', 'contents', ['content_id'], ['id'], ondelete='CASCADE')
    
    op.drop_constraint(op.f('content_locations_location_id_fkey'), 'content_locations', type_='foreignkey')
    op.drop_constraint(op.f('content_locations_content_id_fkey'), 'content_locations', type_='foreignkey')
    op.create_foreign_key(None, 'content_locations', 'contents', ['content_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key(None, 'content_locations', 'locations', ['location_id'], ['id'], ondelete='CASCADE')
    
    op.alter_column('contents', 'published_at',
               existing_type=postgresql.TIMESTAMP(),
               type_=postgresql.TIMESTAMP(timezone=True),
               existing_nullable=False)
    op.alter_column('contents', 'ingested_at',
               existing_type=postgresql.TIMESTAMP(),
               type_=postgresql.TIMESTAMP(timezone=True),
               existing_nullable=True)
    op.alter_column('contents', 'is_active',
               existing_type=sa.BOOLEAN(),
               nullable=False)
    op.alter_column('contents', 'is_published',
               existing_type=sa.BOOLEAN(),
               nullable=False)
    op.alter_column('contents', 'comment_count',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.alter_column('contents', 'view_count',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.alter_column('contents', 'score',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=False)
    op.alter_column('contents', 'review_score',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=False)
    op.alter_column('contents', 'review_count',
               existing_type=sa.INTEGER(),
               nullable=False)
    
    # Note: We keep all valuable content indexes (like search_vector, price_tier_id, etc.) intact!
    op.drop_constraint(op.f('contents_section_id_fkey'), 'contents', type_='foreignkey')
    op.drop_constraint(op.f('contents_price_tier_id_fkey'), 'contents', type_='foreignkey')
    op.drop_constraint(op.f('contents_category_id_fkey'), 'contents', type_='foreignkey')
    op.drop_constraint(op.f('contents_source_id_fkey'), 'contents', type_='foreignkey')
    op.drop_constraint(op.f('contents_intent_id_fkey'), 'contents', type_='foreignkey')
    op.drop_constraint(op.f('contents_gender_id_fkey'), 'contents', type_='foreignkey')
    op.create_foreign_key(None, 'contents', 'sources', ['source_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key(None, 'contents', 'categories', ['category_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key(None, 'contents', 'intent_facets', ['intent_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key(None, 'contents', 'sections', ['section_id'], ['id'], ondelete='RESTRICT')
    op.create_foreign_key(None, 'contents', 'gender_facets', ['gender_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key(None, 'contents', 'price_tier_facets', ['price_tier_id'], ['id'], ondelete='SET NULL')
    
    op.alter_column('distribution_platforms', 'is_active',
               existing_type=sa.BOOLEAN(),
               nullable=False)
    op.alter_column('distribution_platforms', 'created_at',
               existing_type=postgresql.TIMESTAMP(),
               type_=postgresql.TIMESTAMP(timezone=True),
               existing_nullable=True)
    op.alter_column('distribution_posts', 'status',
               existing_type=sa.VARCHAR(length=20),
               nullable=False)
    op.alter_column('distribution_posts', 'publish_date',
               existing_type=postgresql.TIMESTAMP(),
               type_=postgresql.TIMESTAMP(timezone=True),
               existing_nullable=True)
    op.alter_column('distribution_posts', 'views_count',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.alter_column('distribution_posts', 'likes_count',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.alter_column('distribution_posts', 'clicks_count',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.alter_column('distribution_posts', 'shares_count',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.alter_column('distribution_posts', 'created_at',
               existing_type=postgresql.TIMESTAMP(),
               type_=postgresql.TIMESTAMP(timezone=True),
               existing_nullable=True)
    op.alter_column('distribution_posts', 'updated_at',
               existing_type=postgresql.TIMESTAMP(),
               type_=postgresql.TIMESTAMP(timezone=True),
               existing_nullable=True)
    
    op.drop_index(op.f('ix_entities_entity_type'), table_name='entities', if_exists=True)
    op.drop_index(op.f('ix_entities_provider'), table_name='entities', if_exists=True)
    op.drop_index(op.f('ix_entities_external_uri'), table_name='entities', if_exists=True)
    op.create_index('ix_entities_external_uri', 'entities', ['external_uri'], unique=False)
    op.drop_index(op.f('ix_entities_slug'), table_name='entities', if_exists=True)
    op.create_index('ix_entities_slug', 'entities', ['slug'], unique=False)
    op.create_index('ix_entities_type', 'entities', ['entity_type'], unique=False)
    op.create_unique_constraint(None, 'entities', ['external_uri'])
    op.create_unique_constraint(None, 'entities', ['slug'])
    
    op.alter_column('events', 'title',
               existing_type=sa.VARCHAR(length=300),
               type_=sa.String(length=255),
               existing_nullable=False)
    op.alter_column('events', 'event_date',
               existing_type=postgresql.TIMESTAMP(),
               type_=postgresql.TIMESTAMP(timezone=True),
               existing_nullable=True)
    op.drop_index(op.f('ix_events_event_date'), table_name='events', if_exists=True)
    op.drop_index(op.f('ix_events_external_uri'), table_name='events', if_exists=True)
    op.drop_column('events', 'last_updated')
    op.drop_column('events', 'article_count')
    op.drop_column('events', 'importance')
    
    op.drop_index(op.f('ix_locations_slug'), table_name='locations', if_exists=True)
    op.create_index('ix_locations_slug', 'locations', ['slug'], unique=False)
    op.create_unique_constraint(None, 'locations', ['slug'])
    
    op.alter_column('newsletter_subscribers', 'is_confirmed',
               existing_type=sa.BOOLEAN(),
               nullable=False)
    op.alter_column('newsletter_subscribers', 'created_at',
               existing_type=postgresql.TIMESTAMP(),
               type_=postgresql.TIMESTAMP(timezone=True),
               existing_nullable=True)
    op.alter_column('newsletter_subscribers', 'unsubscribed_at',
               existing_type=postgresql.TIMESTAMP(),
               type_=postgresql.TIMESTAMP(timezone=True),
               existing_nullable=True)
    op.create_index('ix_newsletter_subscribers_email', 'newsletter_subscribers', ['email'], unique=False)
    
    op.alter_column('reactions', 'target_type',
               existing_type=sa.VARCHAR(length=50),
               type_=sa.String(length=20),
               existing_nullable=False)
    op.alter_column('reactions', 'created_at',
               existing_type=postgresql.TIMESTAMP(),
               type_=postgresql.TIMESTAMP(timezone=True),
               existing_nullable=True)
    
    op.alter_column('recommendation_clicks', 'created_at',
               existing_type=postgresql.TIMESTAMP(),
               type_=postgresql.TIMESTAMP(timezone=True),
               existing_nullable=True,
               existing_server_default=sa.text('now()'))
    op.drop_index(op.f('ix_recommendation_clicks_created_at'), table_name='recommendation_clicks', if_exists=True)
    op.create_index('ix_rec_clicks_created', 'recommendation_clicks', ['created_at'], unique=False)
    
    op.alter_column('recommendation_impressions', 'created_at',
               existing_type=postgresql.TIMESTAMP(),
               type_=postgresql.TIMESTAMP(timezone=True),
               existing_nullable=True,
               existing_server_default=sa.text('now()'))
    op.drop_index(op.f('ix_recommendation_impressions_created_at'), table_name='recommendation_impressions', if_exists=True)
    op.create_index('ix_rec_impressions_created', 'recommendation_impressions', ['created_at'], unique=False)
    
    op.alter_column('saves', 'created_at',
               existing_type=postgresql.TIMESTAMP(),
               type_=postgresql.TIMESTAMP(timezone=True),
               existing_nullable=True)
    op.alter_column('sections', 'is_active',
               existing_type=sa.BOOLEAN(),
               nullable=False)
    op.alter_column('sections', 'sort_order',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.alter_column('shares', 'created_at',
               existing_type=postgresql.TIMESTAMP(),
               type_=postgresql.TIMESTAMP(timezone=True),
               existing_nullable=True)
    op.drop_index(op.f('ix_share_user_created'), table_name='shares', if_exists=True)
    
    op.alter_column('sources', 'is_active',
               existing_type=sa.BOOLEAN(),
               nullable=False)
    op.drop_index(op.f('ix_sources_domain'), table_name='sources', if_exists=True)
    op.create_index('ix_sources_domain', 'sources', ['domain'], unique=False)
    op.drop_index(op.f('ix_sources_external_uri'), table_name='sources', if_exists=True)
    op.create_index('ix_sources_external_uri', 'sources', ['external_uri'], unique=False)
    op.drop_index(op.f('ix_sources_slug'), table_name='sources', if_exists=True)
    op.create_index('ix_sources_slug', 'sources', ['slug'], unique=False)
    op.create_unique_constraint(None, 'sources', ['external_uri'])
    op.create_unique_constraint(None, 'sources', ['slug'])
    op.create_unique_constraint(None, 'sources', ['domain'])
    
    op.alter_column('user_entity_interests', 'score',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=False)
    op.create_foreign_key(None, 'user_entity_interests', 'entities', ['entity_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key(None, 'user_entity_interests', 'categories', ['category_id'], ['id'], ondelete='CASCADE')
    
    op.alter_column('user_interests', 'interaction_count',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.alter_column('user_interests', 'last_interaction_at',
               existing_type=postgresql.TIMESTAMP(),
               type_=postgresql.TIMESTAMP(timezone=True),
               existing_nullable=True)
    
    op.alter_column('users', 'created_at',
               existing_type=postgresql.TIMESTAMP(),
               type_=postgresql.TIMESTAMP(timezone=True),
               existing_nullable=True)
    op.create_index('ix_users_email', 'users', ['email'], unique=False)
    
    op.alter_column('video_comments', 'like_count',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.alter_column('video_comments', 'reply_count',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.alter_column('video_comments', 'published_at',
               existing_type=postgresql.TIMESTAMP(),
               type_=postgresql.TIMESTAMP(timezone=True),
               existing_nullable=True)
    op.alter_column('video_comments', 'updated_at',
               existing_type=postgresql.TIMESTAMP(),
               type_=postgresql.TIMESTAMP(timezone=True),
               existing_nullable=True)
    op.drop_index(op.f('ix_video_comments_external_id'), table_name='video_comments', if_exists=True)
    op.create_index('ix_video_comments_external_id', 'video_comments', ['external_id'], unique=False)
    op.create_unique_constraint(None, 'video_comments', ['external_id'])
    
    op.alter_column('videos', 'description_display_rule',
               existing_type=sa.VARCHAR(length=20),
               nullable=False)
    op.alter_column('videos', 'published_at',
               existing_type=postgresql.TIMESTAMP(),
               type_=postgresql.TIMESTAMP(timezone=True),
               existing_nullable=True)
    op.alter_column('videos', 'view_count',
               existing_type=sa.BIGINT(),
               nullable=False)
    op.alter_column('videos', 'like_count',
               existing_type=sa.BIGINT(),
               nullable=False)
    op.alter_column('videos', 'comments_count',
               existing_type=sa.INTEGER(),
               nullable=False)
    op.drop_index(op.f('ix_videos_platform'), table_name='videos', if_exists=True)
    op.drop_index(op.f('ix_videos_published_at'), table_name='videos', if_exists=True)
    
    op.alter_column('views', 'created_at',
               existing_type=postgresql.TIMESTAMP(),
               type_=postgresql.TIMESTAMP(timezone=True),
               existing_nullable=True)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('views', 'created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               type_=postgresql.TIMESTAMP(),
               existing_nullable=True)
    op.create_index(op.f('ix_videos_published_at'), 'videos', ['published_at'], unique=False)
    op.create_index(op.f('ix_videos_platform'), 'videos', ['platform'], unique=False)
    op.alter_column('videos', 'comments_count',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.alter_column('videos', 'like_count',
               existing_type=sa.BIGINT(),
               nullable=True)
    op.alter_column('videos', 'view_count',
               existing_type=sa.BIGINT(),
               nullable=True)
    op.alter_column('videos', 'published_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               type_=postgresql.TIMESTAMP(),
               existing_nullable=True)
    op.alter_column('videos', 'description_display_rule',
               existing_type=sa.VARCHAR(length=20),
               nullable=True)
    op.drop_constraint(None, 'video_comments', type_='unique')
    op.drop_index('ix_video_comments_external_id', table_name='video_comments')
    op.create_index(op.f('ix_video_comments_external_id'), 'video_comments', ['external_id'], unique=True)
    op.alter_column('video_comments', 'updated_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               type_=postgresql.TIMESTAMP(),
               existing_nullable=True)
    op.alter_column('video_comments', 'published_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               type_=postgresql.TIMESTAMP(),
               existing_nullable=True)
    op.alter_column('video_comments', 'reply_count',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.alter_column('video_comments', 'like_count',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.drop_index('ix_users_email', table_name='users')
    op.alter_column('users', 'created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               type_=postgresql.TIMESTAMP(),
               existing_nullable=True)
    op.alter_column('user_interests', 'last_interaction_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               type_=postgresql.TIMESTAMP(),
               existing_nullable=True)
    op.alter_column('user_interests', 'interaction_count',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.drop_constraint(None, 'user_entity_interests', type_='foreignkey')
    op.drop_constraint(None, 'user_entity_interests', type_='foreignkey')
    op.alter_column('user_entity_interests', 'score',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=True)
    op.drop_constraint(None, 'sources', type_='unique')
    op.drop_constraint(None, 'sources', type_='unique')
    op.drop_constraint(None, 'sources', type_='unique')
    op.drop_index('ix_sources_slug', table_name='sources')
    op.create_index(op.f('ix_sources_slug'), 'sources', ['slug'], unique=True)
    op.drop_index('ix_sources_external_uri', table_name='sources')
    op.create_index(op.f('ix_sources_external_uri'), 'sources', ['external_uri'], unique=True)
    op.drop_index('ix_sources_domain', table_name='sources')
    op.create_index(op.f('ix_sources_domain'), 'sources', ['domain'], unique=True)
    op.alter_column('sources', 'is_active',
               existing_type=sa.BOOLEAN(),
               nullable=True)
    op.create_index(op.f('ix_share_user_created'), 'shares', ['user_id', 'created_at'], unique=False)
    op.alter_column('shares', 'created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               type_=postgresql.TIMESTAMP(),
               existing_nullable=True)
    op.alter_column('sections', 'sort_order',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.alter_column('sections', 'is_active',
               existing_type=sa.BOOLEAN(),
               nullable=True)
    op.alter_column('saves', 'created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               type_=postgresql.TIMESTAMP(),
               existing_nullable=True)
    op.drop_index('ix_rec_impressions_created', table_name='recommendation_impressions')
    op.create_index(op.f('ix_recommendation_impressions_created_at'), 'recommendation_impressions', ['created_at'], unique=False)
    op.alter_column('recommendation_impressions', 'created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               type_=postgresql.TIMESTAMP(),
               existing_nullable=True,
               existing_server_default=sa.text('now()'))
    op.drop_index('ix_rec_clicks_created', table_name='recommendation_clicks')
    op.create_index(op.f('ix_recommendation_clicks_created_at'), 'recommendation_clicks', ['created_at'], unique=False)
    op.alter_column('recommendation_clicks', 'created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               type_=postgresql.TIMESTAMP(),
               existing_nullable=True,
               existing_server_default=sa.text('now()'))
    op.alter_column('reactions', 'created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               type_=postgresql.TIMESTAMP(),
               existing_nullable=True)
    op.alter_column('reactions', 'target_type',
               existing_type=sa.String(length=20),
               type_=sa.VARCHAR(length=50),
               existing_nullable=False)
    op.drop_index('ix_newsletter_subscribers_email', table_name='newsletter_subscribers')
    op.alter_column('newsletter_subscribers', 'unsubscribed_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               type_=postgresql.TIMESTAMP(),
               existing_nullable=True)
    op.alter_column('newsletter_subscribers', 'created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               type_=postgresql.TIMESTAMP(),
               existing_nullable=True)
    op.alter_column('newsletter_subscribers', 'is_confirmed',
               existing_type=sa.BOOLEAN(),
               nullable=True)
    op.drop_constraint(None, 'locations', type_='unique')
    op.drop_index('ix_locations_slug', table_name='locations')
    op.create_index(op.f('ix_locations_slug'), 'locations', ['slug'], unique=True)
    op.add_column('events', sa.Column('importance', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=True))
    op.add_column('events', sa.Column('article_count', sa.INTEGER(), autoincrement=False, nullable=True))
    op.add_column('events', sa.Column('last_updated', postgresql.TIMESTAMP(), autoincrement=False, nullable=True))
    op.create_index(op.f('ix_events_external_uri'), 'events', ['external_uri'], unique=True)
    op.create_index(op.f('ix_events_event_date'), 'events', ['event_date'], unique=False)
    op.alter_column('events', 'event_date',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               type_=postgresql.TIMESTAMP(),
               existing_nullable=True)
    op.alter_column('events', 'title',
               existing_type=sa.String(length=255),
               type_=sa.VARCHAR(length=300),
               existing_nullable=False)
    op.drop_constraint(None, 'entities', type_='unique')
    op.drop_constraint(None, 'entities', type_='unique')
    op.drop_index('ix_entities_type', table_name='entities')
    op.drop_index('ix_entities_slug', table_name='entities')
    op.create_index(op.f('ix_entities_slug'), 'entities', ['slug'], unique=True)
    op.drop_index('ix_entities_external_uri', table_name='entities')
    op.create_index(op.f('ix_entities_external_uri'), 'entities', ['external_uri'], unique=True)
    op.create_index(op.f('ix_entities_provider'), 'entities', ['provider'], unique=False)
    op.create_index(op.f('ix_entities_entity_type'), 'entities', ['entity_type'], unique=False)
    op.alter_column('distribution_posts', 'updated_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               type_=postgresql.TIMESTAMP(),
               existing_nullable=True)
    op.alter_column('distribution_posts', 'created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               type_=postgresql.TIMESTAMP(),
               existing_nullable=True)
    op.alter_column('distribution_posts', 'shares_count',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.alter_column('distribution_posts', 'clicks_count',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.alter_column('distribution_posts', 'likes_count',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.alter_column('distribution_posts', 'views_count',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.alter_column('distribution_posts', 'publish_date',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               type_=postgresql.TIMESTAMP(),
               existing_nullable=True)
    op.alter_column('distribution_posts', 'status',
               existing_type=sa.VARCHAR(length=20),
               nullable=True)
    op.alter_column('distribution_platforms', 'created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               type_=postgresql.TIMESTAMP(),
               existing_nullable=True)
    op.alter_column('distribution_platforms', 'is_active',
               existing_type=sa.BOOLEAN(),
               nullable=True)
    op.drop_constraint(None, 'contents', type_='foreignkey')
    op.drop_constraint(None, 'contents', type_='foreignkey')
    op.drop_constraint(None, 'contents', type_='foreignkey')
    op.drop_constraint(None, 'contents', type_='foreignkey')
    op.drop_constraint(None, 'contents', type_='foreignkey')
    op.drop_constraint(None, 'contents', type_='foreignkey')
    op.create_foreign_key(op.f('contents_gender_id_fkey'), 'contents', 'gender_facets', ['gender_id'], ['id'])
    op.create_foreign_key(op.f('contents_intent_id_fkey'), 'contents', 'intent_facets', ['intent_id'], ['id'])
    op.create_foreign_key(op.f('contents_source_id_fkey'), 'contents', 'sources', ['source_id'], ['id'])
    op.create_foreign_key(op.f('contents_category_id_fkey'), 'contents', 'categories', ['category_id'], ['id'])
    op.create_foreign_key(op.f('contents_price_tier_id_fkey'), 'contents', 'price_tier_facets', ['price_tier_id'], ['id'])
    op.create_foreign_key(op.f('contents_section_id_fkey'), 'contents', 'sections', ['section_id'], ['id'])
    
    op.alter_column('contents', 'review_count',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.alter_column('contents', 'review_score',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=True)
    op.alter_column('contents', 'score',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=True)
    op.alter_column('contents', 'view_count',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.alter_column('contents', 'comment_count',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.alter_column('contents', 'is_published',
               existing_type=sa.BOOLEAN(),
               nullable=True)
    op.alter_column('contents', 'is_active',
               existing_type=sa.BOOLEAN(),
               nullable=True)
    op.alter_column('contents', 'ingested_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               type_=postgresql.TIMESTAMP(),
               existing_nullable=True)
    op.alter_column('contents', 'published_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               type_=postgresql.TIMESTAMP(),
               existing_nullable=False)
    
    op.drop_constraint(None, 'content_locations', type_='foreignkey')
    op.drop_constraint(None, 'content_locations', type_='foreignkey')
    op.create_foreign_key(op.f('content_locations_content_id_fkey'), 'content_locations', 'contents', ['content_id'], ['id'])
    op.create_foreign_key(op.f('content_locations_location_id_fkey'), 'content_locations', 'locations', ['location_id'], ['id'])
    
    op.drop_constraint(None, 'content_entities', type_='foreignkey')
    op.drop_constraint(None, 'content_entities', type_='foreignkey')
    op.create_foreign_key(op.f('content_entities_entity_id_fkey'), 'content_entities', 'entities', ['entity_id'], ['id'])
    op.create_foreign_key(op.f('content_entities_content_id_fkey'), 'content_entities', 'contents', ['content_id'], ['id'])
    op.drop_index(op.f('ix_content_entities_origin'), table_name='content_entities')
    
    op.alter_column('contact_messages', 'created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               type_=postgresql.TIMESTAMP(),
               existing_nullable=True)
    op.alter_column('comments', 'created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               type_=postgresql.TIMESTAMP(),
               existing_nullable=True)
    
    op.drop_constraint(None, 'categories', type_='unique')
    op.drop_constraint(None, 'categories', type_='unique')
    op.drop_index('ix_categories_slug', table_name='categories')
    op.create_index(op.f('ix_categories_slug'), 'categories', ['slug'], unique=True)
    op.drop_index('ix_categories_external_uri', table_name='categories')
    op.create_index(op.f('ix_categories_external_uri'), 'categories', ['external_uri'], unique=True)
    op.alter_column('categories', 'is_leaf',
               existing_type=sa.BOOLEAN(),
               nullable=True)
    op.alter_column('categories', 'sort_order',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.alter_column('categories', 'is_active',
               existing_type=sa.BOOLEAN(),
               nullable=True)
    
    op.drop_constraint(None, 'authors', type_='unique')
    op.drop_index('ix_authors_slug', table_name='authors')
    op.create_index(op.f('ix_authors_slug'), 'authors', ['slug'], unique=True)
    op.alter_column('authors', 'is_agency',
               existing_type=sa.BOOLEAN(),
               nullable=True)
    op.alter_column('authors', 'slug',
               existing_type=sa.VARCHAR(length=255),
               nullable=True)
    
    op.drop_constraint(None, 'articles', type_='foreignkey')
    op.create_foreign_key(op.f('fk_articles_primary_source_id'), 'articles', 'article_sources', ['primary_source_id'], ['id'])
    op.create_foreign_key(op.f('fk_articles_event_id'), 'articles', 'events', ['event_id'], ['id'])
    op.alter_column('articles', 'last_enrichment_attempt',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               type_=postgresql.TIMESTAMP(),
               existing_nullable=True)
    op.alter_column('articles', 'status',
               existing_type=sa.VARCHAR(length=20),
               nullable=True)
    op.alter_column('articles', 'extended_metadata',
               existing_type=postgresql.JSON(astext_type=sa.Text()),
               comment='Raw provider-specific payload for debugging/auditing only. Do NOT use for routing or queries. Structured data (entities, categories, events) belongs in proper relational tables.',
               existing_nullable=True)
    op.alter_column('articles', 'enrichment_priority',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=True,
               comment='Priority score for enrichment worker. Calculated before enrichment.')
    op.alter_column('articles', 'quality_score',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=True)
    
    op.drop_constraint(None, 'article_sources', type_='foreignkey')
    op.drop_constraint(None, 'article_sources', type_='foreignkey')
    op.create_foreign_key(op.f('article_sources_source_id_fkey'), 'article_sources', 'sources', ['source_id'], ['id'])
    op.create_foreign_key(op.f('article_sources_article_id_fkey'), 'article_sources', 'articles', ['article_id'], ['id'])
    op.alter_column('article_sources', 'published_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               type_=postgresql.TIMESTAMP(),
               existing_nullable=True)
    
    op.drop_constraint(None, 'article_categories', type_='foreignkey')
    op.drop_constraint(None, 'article_categories', type_='foreignkey')
    op.create_foreign_key(op.f('article_categories_article_id_fkey'), 'article_categories', 'articles', ['article_id'], ['id'])
    op.create_foreign_key(op.f('article_categories_category_id_fkey'), 'article_categories', 'categories', ['category_id'], ['id'])
    op.alter_column('article_categories', 'weight',
               existing_type=sa.DOUBLE_PRECISION(precision=53),
               nullable=True)
    
    op.drop_constraint(None, 'article_authors', type_='foreignkey')
    op.drop_constraint(None, 'article_authors', type_='foreignkey')
    op.create_foreign_key(op.f('article_authors_article_id_fkey'), 'article_authors', 'articles', ['article_id'], ['id'])
    op.create_foreign_key(op.f('article_authors_author_id_fkey'), 'article_authors', 'authors', ['author_id'], ['id'])
    # ### end Alembic commands ###