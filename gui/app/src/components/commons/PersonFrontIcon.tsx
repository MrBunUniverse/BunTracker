import { BodyPart } from 'solarxr-protocol';

export const SIDES = [
  {
    shoulder: BodyPart.LEFT_SHOULDER,
    upperArm: BodyPart.LEFT_UPPER_ARM,
    lowerArm: BodyPart.LEFT_LOWER_ARM,
    hand: BodyPart.LEFT_HAND,
    upperLeg: BodyPart.LEFT_UPPER_LEG,
    lowerLeg: BodyPart.LEFT_LOWER_LEG,
    foot: BodyPart.LEFT_FOOT,
  },
  {
    shoulder: BodyPart.RIGHT_SHOULDER,
    upperArm: BodyPart.RIGHT_UPPER_ARM,
    lowerArm: BodyPart.RIGHT_LOWER_ARM,
    hand: BodyPart.RIGHT_HAND,
    upperLeg: BodyPart.RIGHT_UPPER_LEG,
    lowerLeg: BodyPart.RIGHT_LOWER_LEG,
    foot: BodyPart.RIGHT_FOOT,
  },
];

export function PersonFrontIcon({ mirror = true }: { mirror?: boolean }) {
  const CIRCLE_RADIUS = 0.0001;
  const left = +!mirror;
  const right = +mirror;

  return (
    <svg
      width="100%"
      viewBox="0 0 163 392"
      className="overflow-visible"
      xmlns="http://www.w3.org/2000/svg"
    >
      <image
        className="h-full w-full"
        style={{
          transform: 'translateY(-18px) scale(1.12)',
          transformOrigin: 'center',
        }}
        href="/images/assignment-pose.webp"
      />
      <circle
        className="body-part-circle"
        cx="82"
        cy="124"
        r={CIRCLE_RADIUS}
        id={BodyPart[BodyPart.UPPER_CHEST]}
      />
      <circle
        className="body-part-circle"
        cx="82"
        cy="138"
        r={CIRCLE_RADIUS}
        id={BodyPart[BodyPart.CHEST]}
      />
      <circle
        className="body-part-circle"
        cx="82"
        cy="181"
        r={CIRCLE_RADIUS}
        id={BodyPart[BodyPart.HIP]}
      />
      <circle
        className="body-part-circle"
        cx="82"
        cy="155"
        r={CIRCLE_RADIUS}
        id={BodyPart[BodyPart.WAIST]}
      />
      <circle
        className="body-part-circle"
        cx="82"
        cy="98"
        r={CIRCLE_RADIUS}
        id={BodyPart[BodyPart.NECK]}
      />
      <circle
        className="body-part-circle"
        cx="82"
        cy="35"
        r={CIRCLE_RADIUS}
        id={BodyPart[BodyPart.HEAD]}
      />
      <circle
        className="body-part-circle"
        cx="134"
        cy="197"
        r={CIRCLE_RADIUS}
        id={BodyPart[SIDES[right].hand]}
      />
      <circle
        className="body-part-circle"
        cx="111"
        cy="142"
        r={CIRCLE_RADIUS}
        id={BodyPart[SIDES[right].upperArm]}
      />
      <circle
        className="body-part-circle"
        cx="104"
        cy="121"
        r={CIRCLE_RADIUS}
        id={BodyPart[SIDES[right].shoulder]}
      />
      <circle
        className="body-part-circle"
        cx="130"
        cy="177"
        r={CIRCLE_RADIUS}
        id={BodyPart[SIDES[right].lowerArm]}
      />
      <circle
        className="body-part-circle"
        cx="99"
        cy="307"
        r={CIRCLE_RADIUS}
        id={BodyPart[SIDES[right].lowerLeg]}
      />
      <circle
        className="body-part-circle"
        cx="98"
        cy="230"
        r={CIRCLE_RADIUS}
        id={BodyPart[SIDES[right].upperLeg]}
      />
      <circle
        className="body-part-circle"
        cx="102"
        cy="380"
        r={CIRCLE_RADIUS}
        id={BodyPart[SIDES[right].foot]}
      />

      <circle
        className="body-part-circle"
        cx="30"
        cy="197"
        r={CIRCLE_RADIUS}
        id={BodyPart[SIDES[left].hand]}
      />

      <circle
        className="body-part-circle"
        cx="53"
        cy="142"
        r={CIRCLE_RADIUS}
        id={BodyPart[SIDES[left].upperArm]}
      />
      <circle
        className="body-part-circle"
        cx="60"
        cy="121"
        r={CIRCLE_RADIUS}
        id={BodyPart[SIDES[left].shoulder]}
      />
      <circle
        className="body-part-circle"
        cx="34"
        cy="177"
        r={CIRCLE_RADIUS}
        id={BodyPart[SIDES[left].lowerArm]}
      />
      <circle
        className="body-part-circle"
        cx="65"
        cy="307"
        r={CIRCLE_RADIUS}
        id={BodyPart[SIDES[left].lowerLeg]}
      />

      <circle
        className="body-part-circle"
        cx="66"
        cy="230"
        r={CIRCLE_RADIUS}
        id={BodyPart[SIDES[left].upperLeg]}
      />
      <circle
        className="body-part-circle"
        cx="62"
        cy="380"
        r={CIRCLE_RADIUS}
        id={BodyPart[SIDES[left].foot]}
      />
    </svg>
  );
}
