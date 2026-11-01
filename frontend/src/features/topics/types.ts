import type {components} from "../../api/generated";
export type Topic = components["schemas"]["TopicSchema"];
export type TopicList = components["schemas"]["TopicListSchema"];
export type TopicAssignment = components["schemas"]["AssignmentSchema"];
export const topicLabel=(topic:Pick<Topic,"name"|"code">)=>[topic.code,topic.name].filter(Boolean).join(" · ");
